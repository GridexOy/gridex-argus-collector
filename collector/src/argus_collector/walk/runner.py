"""The walk loop: browser + evidence + extraction + model, one page at a time."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field

from argus_collector.browser import contract as browser
from argus_collector.discovery import contract as discovery
from argus_collector.evidence import contract as evidence
from argus_collector.extraction import contract as extraction
from argus_collector.models import contract as models
from argus_collector.storage import contract as storage
from argus_collector.walk import repository, service
from argus_collector.walk.service import Action, WalkEvent, WalkSettings, WalkSummary

Emit = Callable[[WalkEvent], None]
ShouldStop = Callable[[], bool]


class StopRequested(Exception):
    """Raised between steps when the owner or the STOP file asked to stop."""


@dataclass
class WalkState:
    settings: WalkSettings
    conn: sqlite3.Connection
    client: models.ModelClient
    emit: Emit
    should_stop: ShouldStop
    run_id: str
    hosts: frozenset[str] = frozenset()
    visited: set[str] = field(default_factory=set)
    seen_keys: set[str] = field(default_factory=set)
    seen_contacts: set[tuple[str, str | None, str | None]] = field(default_factory=set)
    pages: int = 0
    contacts: int = 0

    def check_stop(self) -> None:
        if self.should_stop() or any(p.exists() for p in self.settings.stop_files):
            raise StopRequested()

    def step(self, step: str, detail: str = "", url: str = "") -> None:
        self.emit(WalkEvent(service.EVENT_STEP, url=url, step=step, detail=detail))


def run(settings: WalkSettings, on_event: Emit, should_stop: ShouldStop) -> WalkSummary:
    conn = storage.connect(settings.db_path)
    client = models.ModelClient(settings.model, conn)
    run_id = repository.start_run(conn, settings.start_url)
    state = WalkState(settings, conn, client, on_event, should_stop, run_id)
    result, error, stopped = "completed", "", False
    try:
        _walk(state)
    except StopRequested:
        result, stopped = "cancelled", True
        on_event(WalkEvent(service.EVENT_STOPPED, detail="stopped"))
    except (browser.BrowserLaunchError, models.ModelError, Exception) as exc:  # noqa: BLE001
        result, error = (
            "failed",
            f"{type(exc).__name__}: {str(exc).splitlines()[0] if str(exc) else ''}",
        )
        on_event(WalkEvent(service.EVENT_ERROR, error=error))
    finally:
        repository.finish_run(conn, run_id, state.pages, state.contacts, result)
        conn.close()
    if not stopped and not error:
        on_event(WalkEvent(service.EVENT_DONE, detail=result, page_no=state.pages))
    return WalkSummary(state.pages, state.contacts, stopped, error, tuple(sorted(state.visited)))


def _walk(state: WalkState) -> None:
    settings = state.settings
    state.step(service.STEP_LOADING, settings.start_url, settings.start_url)
    with browser.WalkBrowser(settings.headless, settings.profile_dir) as wb:
        page = wb.goto(settings.start_url)
        state.hosts = discovery.approved_hosts_for(settings.start_url, page.url)
        while True:
            state.check_stop()
            action = _handle_page(state, page)
            if action.kind == service.ACTION_FINISH:
                return
            state.check_stop()
            page = _perform(state, wb, page, action)


def _handle_page(state: WalkState, page: browser.PageState) -> Action:
    """Observe one page (budget counted per new URL), extract, decide."""
    url_key = discovery.normalize_url(page.url)
    if url_key not in state.visited:
        if state.pages >= state.settings.page_budget:
            return Action(service.ACTION_FINISH)
        state.pages += 1
        state.visited.add(url_key)
    state.emit(
        WalkEvent(
            service.EVENT_PAGE, url=page.url, page_no=state.pages, budget=state.settings.page_budget
        )
    )
    text = evidence.canonical_text(page.text)
    key = discovery.page_key(page.url, evidence.sha256_text(text))
    if key in state.seen_keys:
        return service.fallback_action(_ranked(state, page))
    state.seen_keys.add(key)
    snapshot = evidence.store_snapshot(
        state.conn, page.url, page.url, page.html, page.text, state.settings.evidence_dir
    )
    state.step(service.STEP_EXTRACTING, "", page.url)
    channels = extraction.extract_channels(page.html, text)
    if extraction.has_contact_signals(text, channels):
        _parse_cards(state, page, text, channels, snapshot.evidence_id)
    state.check_stop()
    return _decide(state, page, text)


def _parse_cards(
    state: WalkState,
    page: browser.PageState,
    text: str,
    channels: list[extraction.Channel],
    evidence_id: str,
) -> None:
    state.step(service.STEP_MODEL, "cards", page.url)
    system, user = service.cards_prompt(page.url, page.title, text)
    try:
        reply = state.client.chat_json(system, user, service.PURPOSE_CARDS)
    except models.ModelError as exc:
        state.step(service.STEP_MODEL, f"cards failed: {exc}", page.url)
        return
    for item in service.cards_from_reply(reply):
        card = extraction.card_from_json(item)
        contact = extraction.verify_card(card, text, channels) if card else None
        if contact is None:
            continue
        key = (
            contact.name.value.casefold(),
            contact.phone.value if contact.phone else None,
            contact.email.value if contact.email else None,
        )
        if key in state.seen_contacts:
            continue
        state.seen_contacts.add(key)
        repository.insert_observation(state.conn, state.run_id, evidence_id, page.url, contact)
        state.contacts += 1
        state.emit(
            WalkEvent(service.EVENT_CONTACT, url=page.url, contact=contact, evidence_id=evidence_id)
        )


def _ranked(state: WalkState, page: browser.PageState) -> list[discovery.Candidate]:
    return discovery.rank_candidates(page.candidates, state.visited, state.hosts)


def _decide(state: WalkState, page: browser.PageState, text: str) -> Action:
    candidates = _ranked(state, page)
    pages_left = state.settings.page_budget - state.pages
    if not candidates or pages_left < 0:
        return Action(service.ACTION_FINISH)
    state.step(service.STEP_MODEL, "action", page.url)
    system, user = service.action_prompt(page.url, page.title, text, candidates, pages_left)
    try:
        reply = state.client.chat_json(system, user, service.PURPOSE_ACTION)
    except models.ModelError as exc:
        state.step(service.STEP_MODEL, f"action failed: {exc}", page.url)
        return service.fallback_action(candidates)
    action = service.parse_action(reply, candidates)
    if action.kind == service.ACTION_NAVIGATE and pages_left == 0:
        return Action(service.ACTION_FINISH)
    return action


def _perform(
    state: WalkState, wb: browser.WalkBrowser, page: browser.PageState, action: Action
) -> browser.PageState:
    if action.kind == service.ACTION_SCROLL:
        state.step(service.STEP_SCROLL, "", page.url)
        return wb.scroll()
    assert action.candidate is not None
    if action.kind == service.ACTION_NAVIGATE:
        state.step(service.STEP_NAVIGATE, action.candidate.href, page.url)
        return wb.goto(action.candidate.href)
    state.step(service.STEP_CLICK, action.candidate.text, page.url)
    return wb.click(action.candidate)
