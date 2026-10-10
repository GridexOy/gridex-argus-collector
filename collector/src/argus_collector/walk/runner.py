"""The walk loop: open, observe a page, the goal, decide, act — until finish, budget or stop.

Before every next action the tally of people read is asked first (`goal.py`,
owner 06.10.2026): the goal reached, or 2 more pages read without it, end the
walk completed.
"""

from __future__ import annotations

from dataclasses import replace

from argus_collector.browser import contract as browser
from argus_collector.discovery import contract as discovery
from argus_collector.models import contract as models
from argus_collector.storage import contract as storage
from argus_collector.walk import country, ending, repository, service, timing
from argus_collector.walk import page as page_step
from argus_collector.walk.actions import gap_reason, goto, perform_safely
from argus_collector.walk.decide import decide, end_budget, end_stalled
from argus_collector.walk.service import Action, WalkEvent, WalkSettings, WalkSummary
from argus_collector.walk.sink import WalkCheckpoint, WalkSink
from argus_collector.walk.state import (
    MAX_STALLED,
    Emit,
    ShouldStop,
    StopRequested,
    WalkState,
)

DOMAIN_GAP = "domain_ownership_unresolved"
CARDS_MAX_TOKENS = 4096  # a window of many cards is one long JSON answer (Ellego, 40 people)
CHALLENGE_GAP = "captcha"  # a bot check that did not clear: needs_attention (8.5)

__all__ = ["StopRequested", "WalkState", "run"]


def _state(
    settings: WalkSettings, on_event: Emit, should_stop: ShouldStop, sink: WalkSink | None
) -> WalkState:
    conn = storage.connect(settings.db_path)
    listener = (lambda record: sink.model_called(conn, record)) if sink is not None else None
    cards = replace(settings.model, max_tokens=max(settings.model.max_tokens, CARDS_MAX_TOKENS))
    client = models.ModelClient(cards, conn, listener)
    run_id = repository.start_run(conn, settings.start_url)
    resume = settings.resume
    cp = WalkCheckpoint.from_json(resume.to_json()) if resume else WalkCheckpoint()
    focus = settings.focus
    if focus is not None and cp.native_language:
        focus = focus.with_native(cp.native_language)
    return WalkState(
        settings, conn, client, on_event, should_stop, run_id, sink, focus=focus, cp=cp,
    )


def run(
    settings: WalkSettings, on_event: Emit, should_stop: ShouldStop, sink: WalkSink | None = None
) -> WalkSummary:
    state = _state(settings, on_event, should_stop, sink)
    result, error, stopped = "completed", "", False
    try:
        _walk(state)
    except StopRequested:
        result, stopped, state.end_reason = "cancelled", True, service.END_STOPPED
        on_event(WalkEvent(service.EVENT_STOPPED, detail="stopped"))
    except Exception as exc:  # noqa: BLE001 - every walk error ends as a reported result
        first = str(exc).splitlines()[0] if str(exc) else ""
        result, error, state.end_reason = "failed", f"{type(exc).__name__}: {first}", "error"
        timing.failed(settings.id_namespace, error)
        on_event(WalkEvent(service.EVENT_ERROR, error=error))
    finally:
        state.tick()
        state.save_checkpoint()
        repository.finish_run(state.conn, state.run_id, state.cp.pages, state.contacts, result)
        state.conn.close()
    if not stopped and not error and state.end_reason != service.END_ATTENTION:
        on_event(ending.done_event(state, result))
    visited = tuple(sorted(state.cp.visited))
    return WalkSummary(
        state.cp.pages, state.contacts, stopped, error, visited, state.end_reason, state.cp
    )


def _walk(state: WalkState) -> None:
    settings = state.settings
    host, profile = settings.browser_host, _after_attention(settings)
    with browser.WalkBrowser(settings.headless, settings.profile_dir, host, profile) as wb:
        timing.chrome(settings.id_namespace, wb.start_ms, host is not None and not profile)
        page = _open(state, wb)
        while page is not None:
            if page.challenge:
                _attention(state, page)
                return
            state.clear_gap(page.url, CHALLENGE_GAP)
            if page.consent:
                state.cp.consents[discovery.host_of(page.url)] = page.consent
                state.step(service.STEP_CONSENT, page.consent.split(": ", 1)[-1], page.url)
            state.check_stop()
            state.tick()
            if state.budget_spent() or not page_step.enter(state, page):
                end_budget(state)
                return
            text, pending = page_step.observe(state, wb, page)
            if pending is None and state.stalled >= MAX_STALLED:
                end_stalled(state, page.url)
                return
            action = _next(state, wb, page, text, pending)
            state.check_stop()
            _flush_timing(state, page.url, action)
            if action.kind == service.ACTION_FINISH:
                return
            state.check_stop()
            with timing.timed(state.timing, "load"):
                page = perform_safely(state, wb, page, action)


def _after_attention(settings: WalkSettings) -> bool:
    """A resume after a bot check the owner passed in the work browser: its cookies are in
    the work-browser profile, so this walk opens that profile, not a clean context."""
    resume = settings.resume
    return resume is not None and any(g.reason == CHALLENGE_GAP for g in resume.gaps)


def _next(state: WalkState, wb: browser.WalkBrowser, page: browser.PageState, text: str,
          pending: page_step.Pending | None) -> Action:
    """The goal first; else the decided step, the page's people read before any navigation
    (the card model works while the step is chosen)."""
    if pending is not None and not pending.read.asks:  # the rules read it: nothing to ask
        page_step.complete(state, wb, page, pending)
        pending = None
    goal_action = ending.after_goal(state, page)
    if goal_action is not None:
        return goal_action
    with timing.timed(state.timing, "action"):
        action = decide(state, wb, page, text)
    page_step.complete(state, wb, page, pending)
    return ending.after_goal(state, page) or action


def _flush_timing(state: WalkState, url: str, action: service.Action) -> None:
    """One `timing:` journal line per handled page state, then a fresh timer."""
    state.timing.decide = action.source or action.kind
    timing.flush(state.settings.id_namespace, url, state.timing)
    state.timing = timing.PageTiming()


def _attention(state: WalkState, page: browser.PageState) -> None:
    """The owner passes the check in the work browser; the run resumes on this URL."""
    detail = f"a bot check on {page.url} did not clear within 20 s"
    state.add_gap(page.url, CHALLENGE_GAP, detail, True)
    state.cp.last_url = page.url
    state.end_reason = service.END_ATTENTION
    state.step(service.STEP_ATTENTION, page.url, page.url)


def _open(state: WalkState, wb: browser.WalkBrowser) -> browser.PageState | None:
    settings = state.settings
    url = state.cp.last_url or settings.start_url
    state.step(service.STEP_LOADING, url, url)
    try:
        with timing.timed(state.timing, "load"):
            page = goto(wb, url)
    except browser.ActionError as exc:
        state.add_gap(url, gap_reason(exc), str(exc).splitlines()[0], True)
        state.end_reason = service.END_START_FAILED
        return None
    hosts = settings.approved_hosts
    state.hosts = hosts if hosts is not None else discovery.approved_hosts_for(url, page.url)
    landed = discovery.host_of(page.url)
    if landed not in state.hosts:
        detail = f"{url} led to {landed}, which is not an approved host"
        state.add_gap(url, DOMAIN_GAP, detail, False)
        state.end_reason = service.END_DOMAIN
        return None
    return country.settle(state, wb, page)
