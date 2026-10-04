"""The walk loop: open, observe a page, decide, act — until finish, budget or stop."""

from __future__ import annotations

import time

from argus_collector.browser import contract as browser
from argus_collector.discovery import contract as discovery
from argus_collector.models import contract as models
from argus_collector.storage import contract as storage
from argus_collector.walk import page as page_step
from argus_collector.walk import repository, service
from argus_collector.walk.decide import decide, end_budget
from argus_collector.walk.service import Action, WalkEvent, WalkSettings, WalkSummary
from argus_collector.walk.sink import WalkCheckpoint, WalkSink
from argus_collector.walk.state import (
    MAX_FAILURES_IN_ROW,
    Emit,
    ShouldStop,
    StopRequested,
    WalkState,
)

RETRY_BACKOFF_S = 2.0  # one retry of a failed navigation (TZ_SELAIN 8.5)
DOMAIN_GAP = "domain_ownership_unresolved"

__all__ = ["StopRequested", "WalkState", "run"]


def _state(
    settings: WalkSettings, on_event: Emit, should_stop: ShouldStop, sink: WalkSink | None
) -> WalkState:
    conn = storage.connect(settings.db_path)
    listener = (lambda record: sink.model_called(conn, record)) if sink is not None else None
    client = models.ModelClient(settings.model, conn, listener)
    run_id = repository.start_run(conn, settings.start_url)
    resume = settings.resume
    cp = WalkCheckpoint.from_json(resume.to_json()) if resume else WalkCheckpoint()
    focus = settings.focus
    if focus is not None and cp.native_language:
        focus = focus.with_native(cp.native_language)
    return WalkState(
        settings, conn, client, on_event, should_stop, run_id, sink, focus=focus, cp=cp
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
    if not stopped and not error:
        on_event(WalkEvent(service.EVENT_DONE, detail=result, page_no=state.cp.pages))
    visited = tuple(sorted(state.cp.visited))
    return WalkSummary(
        state.cp.pages, state.contacts, stopped, error, visited, state.end_reason, state.cp
    )


def _walk(state: WalkState) -> None:
    settings = state.settings
    with browser.WalkBrowser(settings.headless, settings.profile_dir) as wb:
        page = _open(state, wb)
        while page is not None:
            state.check_stop()
            state.tick()
            if state.budget_spent() or not page_step.enter(state, page):
                end_budget(state)
                return
            text = page_step.observe(state, wb, page)
            state.check_stop()
            action = decide(state, page, text)
            if action.kind == service.ACTION_FINISH:
                return
            state.check_stop()
            page = _perform_safely(state, wb, page, action)


def _gap_reason(exc: Exception) -> str:
    message = str(exc)
    if "timeout" in message.lower() or "timed out" in message:
        return "timeout"
    if "net::" in message or "ERR_" in message:
        return "network_error"
    return "unsupported_widget"


def _goto(wb: browser.WalkBrowser, url: str) -> browser.PageState:
    try:
        return wb.goto(url)
    except browser.ActionError:
        time.sleep(RETRY_BACKOFF_S)
        return wb.goto(url)


def _open(state: WalkState, wb: browser.WalkBrowser) -> browser.PageState | None:
    settings = state.settings
    url = state.cp.last_url or settings.start_url
    state.step(service.STEP_LOADING, url, url)
    try:
        page = _goto(wb, url)
    except browser.ActionError as exc:
        state.add_gap(url, _gap_reason(exc), str(exc).splitlines()[0], True)
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


def _failed(state: WalkState, action: Action, page: browser.PageState, exc: Exception) -> None:
    cand = action.candidate
    target = (cand.href or cand.selector) if cand else page.url
    if cand is not None and cand.href:
        state.cp.frontier.pop(discovery.normalize_url(cand.href), None)
        state.failed_targets.add(discovery.normalize_url(cand.href))
    elif cand is not None:
        state.failed_targets.add(cand.selector)
    state.add_gap(cand.href if cand and cand.href else page.url, _gap_reason(exc),
                  f"{action.kind} {target}: {str(exc).splitlines()[0][:200]}", True)
    state.failures_in_row += 1


def _perform_safely(
    state: WalkState, wb: browser.WalkBrowser, page: browser.PageState, action: Action
) -> browser.PageState | None:
    """A failed action is a gap and the walk goes on; three in a row end it."""
    state.cp.actions += 1
    try:
        new_page = _perform(state, wb, page, action)
    except browser.ActionError as exc:
        _failed(state, action, page, exc)
        if state.failures_in_row >= MAX_FAILURES_IN_ROW:
            state.end_reason = service.END_FAILURES
            return None
        try:
            return wb.observe()
        except browser.ActionError:
            state.end_reason = service.END_FAILURES
            return None
    state.failures_in_row = 0
    if discovery.host_of(new_page.url) in state.hosts:
        return new_page
    state.add_gap(new_page.url, DOMAIN_GAP, f"an action on {page.url} left the approved hosts",
                  False)
    try:
        return wb.back()
    except browser.ActionError:
        return None


def _perform(
    state: WalkState, wb: browser.WalkBrowser, page: browser.PageState, action: Action
) -> browser.PageState:
    if action.kind == service.ACTION_SCROLL:
        state.step(service.STEP_SCROLL, "", page.url)
        return wb.scroll()
    assert action.candidate is not None
    if action.kind == service.ACTION_NAVIGATE:
        state.step(service.STEP_NAVIGATE, action.candidate.href, page.url)
        return _goto(wb, action.candidate.href)
    state.step(service.STEP_CLICK, action.candidate.text, page.url)
    return wb.click(action.candidate)
