"""The walk loop: open, observe a page, decide, act — until finish, budget or stop."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from argus_collector.browser import contract as browser
from argus_collector.discovery import contract as discovery
from argus_collector.models import contract as models
from argus_collector.storage import contract as storage
from argus_collector.walk import page as page_step
from argus_collector.walk import repository, service, timing, vision
from argus_collector.walk.actions import gap_reason, goto, perform_safely
from argus_collector.walk.decide import decide, end_budget
from argus_collector.walk.service import WalkEvent, WalkSettings, WalkSummary
from argus_collector.walk.sink import WalkCheckpoint, WalkSink
from argus_collector.walk.state import (
    Emit,
    ShouldStop,
    StopRequested,
    WalkState,
)

DOMAIN_GAP = "domain_ownership_unresolved"
MODEL_WORKERS = 3  # card-model windows at a time (OLLAMA_NUM_PARALLEL=3, owner 05.10.2026)
CHALLENGE_GAP = "captcha"  # a bot check that did not clear: needs_attention (8.5)

__all__ = ["StopRequested", "WalkState", "run"]


def _state(
    settings: WalkSettings, on_event: Emit, should_stop: ShouldStop, sink: WalkSink | None
) -> WalkState:
    conn = storage.connect(settings.db_path)
    listener = (lambda record: sink.model_called(conn, record)) if sink is not None else None
    client = models.ModelClient(settings.model, conn, listener)
    nav = settings.navigation
    nav_client = models.ModelClient(nav, conn, listener) if nav and nav != settings.model else None
    vision = settings.vision
    vision_client = models.ModelClient(vision, conn, listener) if vision else None
    run_id = repository.start_run(conn, settings.start_url)
    resume = settings.resume
    cp = WalkCheckpoint.from_json(resume.to_json()) if resume else WalkCheckpoint()
    focus = settings.focus
    if focus is not None and cp.native_language:
        focus = focus.with_native(cp.native_language)
    return WalkState(
        settings, conn, client, on_event, should_stop, run_id, sink, focus=focus, cp=cp,
        nav_client=nav_client, vision_client=vision_client,
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
        on_event(WalkEvent(service.EVENT_ERROR, error=error))
    finally:
        state.tick()
        state.save_checkpoint()
        repository.finish_run(state.conn, state.run_id, state.cp.pages, state.contacts, result)
        state.conn.close()
    if not stopped and not error and state.end_reason != service.END_ATTENTION:
        on_event(WalkEvent(service.EVENT_DONE, detail=result, page_no=state.cp.pages))
    visited = tuple(sorted(state.cp.visited))
    return WalkSummary(
        state.cp.pages, state.contacts, stopped, error, visited, state.end_reason, state.cp
    )


def _walk(state: WalkState) -> None:
    settings = state.settings
    with browser.WalkBrowser(settings.headless, settings.profile_dir) as wb, \
            ThreadPoolExecutor(MODEL_WORKERS, thread_name_prefix="walk-model") as pool:
        state.pool = pool
        page = _open(state, wb)
        while page is not None:
            page = _vision_bot_check(state, wb, page)
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
            with timing.timed(state.timing, "action"):
                action = decide(state, wb, page, text)  # the card model works meanwhile
            page_step.complete(state, wb, page, pending)  # extracted before any navigation
            state.check_stop()
            _flush_timing(state, page.url, action)
            if action.kind == service.ACTION_FINISH:
                return
            state.check_stop()
            with timing.timed(state.timing, "load"):
                page = perform_safely(state, wb, page, action)


def _vision_bot_check(
    state: WalkState, wb: browser.WalkBrowser, page: browser.PageState
) -> browser.PageState:
    """One bot-check sign and the vision model sees a check: wait it out like one."""
    if not vision.is_bot_check(state, wb, page):
        return page
    try:
        with timing.timed(state.timing, "load"):
            return wb.wait_out_challenge()
    except browser.ActionError:
        return page


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
    return page
