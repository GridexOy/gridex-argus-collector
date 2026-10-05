"""Performing one action of a walk: navigate, click, select, scroll (TZ_SELAIN 8.4).

A failed action is a gap (`timeout` / `network_error` / `unsupported_widget`)
and the walk goes on; three failures in a row end it, and the relevant links
still in the frontier become gaps `no_progress`. An action that leaves the
approved hosts is a gap `domain_ownership_unresolved` and the walk goes back.
"""

from __future__ import annotations

import time

from argus_collector.browser import contract as browser
from argus_collector.discovery import contract as discovery
from argus_collector.walk import service
from argus_collector.walk.service import Action
from argus_collector.walk.state import MAX_FAILURES_IN_ROW, WalkState

RETRY_BACKOFF_S = 2.0  # one retry of a failed navigation (TZ_SELAIN 8.5)
DOMAIN_GAP = "domain_ownership_unresolved"


def goto(wb: browser.WalkBrowser, url: str) -> browser.PageState:
    try:
        return wb.goto(url)
    except browser.ActionError:
        time.sleep(RETRY_BACKOFF_S)
        return wb.goto(url)


def gap_reason(exc: Exception) -> str:
    message = str(exc)
    if "timeout" in message.lower() or "timed out" in message:
        return "timeout"
    if "net::" in message or "ERR_" in message:
        return "network_error"
    return "unsupported_widget"


def _failed(state: WalkState, action: Action, page: browser.PageState, exc: Exception) -> None:
    cand = action.candidate
    target = (cand.href or cand.selector) if cand else page.url
    if cand is not None and cand.href:
        state.cp.frontier.pop(discovery.normalize_url(cand.href), None)
        state.failed_targets.add(discovery.normalize_url(cand.href))
    elif cand is not None:
        state.failed_targets.add(cand.selector)
    state.add_gap(cand.href if cand and cand.href else page.url, gap_reason(exc),
                  f"{action.kind} {target}: {str(exc).splitlines()[0][:200]}", True)
    state.failures_in_row += 1


def perform_safely(
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
            state.gap_unwalked("no_progress", "the walk ended after three failed actions")
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
    if action.kind == service.ACTION_SELECT:
        state.step(service.STEP_CLICK, f"{action.candidate.text}: {action.option}", page.url)
        return wb.select(action.candidate, action.option)
    if action.kind == service.ACTION_NAVIGATE:
        state.step(service.STEP_NAVIGATE, action.candidate.href, page.url)
        return goto(wb, action.candidate.href)
    state.step(service.STEP_CLICK, action.candidate.text, page.url)
    return wb.click(action.candidate)
