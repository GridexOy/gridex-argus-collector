"""One observed page: budget, snapshot, channels, model cards, findings, record."""

from __future__ import annotations

from argus_collector.browser import contract as browser
from argus_collector.discovery import contract as discovery
from argus_collector.evidence import contract as evidence
from argus_collector.extraction import contract as extraction
from argus_collector.models import contract as models
from argus_collector.normalization import contract as norm
from argus_collector.storage import contract as storage
from argus_collector.walk import findings, prompts, repository, service
from argus_collector.walk.service import WalkEvent
from argus_collector.walk.sink import PageFindings, PageSource
from argus_collector.walk.state import WalkState

MAX_LINKS_SHOWN = 30
MAX_BUTTONS_SHOWN = 10


def enter(state: WalkState, page: browser.PageState) -> bool:
    """Count a new URL against the page budget; False when the budget is used up."""
    key = discovery.normalize_url(page.url)
    if key not in state.cp.visited:
        if state.cp.pages >= state.settings.run_limits().pages:
            state.end_reason = service.END_BUDGET
            return False
        state.cp.pages += 1
        state.mark_visited(page.url)
    budget = state.settings.run_limits().pages
    state.emit(WalkEvent(service.EVENT_PAGE, url=page.url, page_no=state.cp.pages, budget=budget))
    return True


def ranked(state: WalkState, page: browser.PageState) -> list[discovery.Candidate]:
    """Page links plus frontier links from earlier pages, then the page's buttons."""
    pool = page.candidates + state.frontier_candidates()
    ordered = discovery.rank_candidates(pool, set(state.cp.visited), state.hosts, state.focus)
    links = [c for c in ordered if c.kind == "link"][:MAX_LINKS_SHOWN]
    buttons = [c for c in ordered if c.kind == "button" and c.selector not in state.failed_targets]
    return links + buttons[:MAX_BUTTONS_SHOWN]


def observe(state: WalkState, wb: browser.WalkBrowser, page: browser.PageState) -> str:
    """Snapshot and extract a page state not seen before; returns its canonical text."""
    text = evidence.canonical_text(page.text)
    key = discovery.page_key(page.url, evidence.sha256_text(text))
    links = discovery.rank_candidates(page.candidates, set(state.cp.visited), state.hosts)
    state.remember_links(page.url, [c for c in links if c.kind == "link"])
    if key not in state.cp.seen_keys:
        state.cp.seen_keys.append(key)
        _extract(state, wb, page, text, key)
    state.cp.last_url = page.url
    state.save_checkpoint()
    return text


def _learn_language(state: WalkState, lang: str) -> None:
    if not state.cp.native_language and lang:
        state.cp.native_language = lang.split("-", 1)[0].lower()[:2]
    if state.focus is not None and not state.focus.native_language and state.cp.native_language:
        state.focus = state.focus.with_native(state.cp.native_language)


def _extract(
    state: WalkState, wb: browser.WalkBrowser, page: browser.PageState, text: str, key: str
) -> None:
    settings = state.settings
    snapshot = evidence.store_snapshot(
        state.conn, page.url, page.url, page.html, page.text, settings.evidence_dir
    )
    source = PageSource(
        state.uid("source", key), state.source_id, page.url, page.url, key, snapshot, text
    )
    state.source_id = source.source_id
    if state.sink is not None:
        state.sink.page_stored(state.conn, source)
    state.step(service.STEP_EXTRACTING, "", page.url)
    lang = extraction.html_language(page.html)
    _learn_language(state, lang)
    region = norm.region_for_page(page.url, lang, settings.region_fallback)
    channels = extraction.extract_channels(page.html, text, region or settings.region_fallback)
    contacts: list[extraction.Contact] = []
    if extraction.has_contact_signals(text, channels):
        contacts = _parse_cards(state, page, text, channels, region or settings.region_fallback)
    bindings = wb.bindings(findings.probes(contacts)) if state.job_mode and contacts else []
    found, keys = findings.build_findings(state, source, contacts, bindings, channels)
    _record(state, source, found, list(zip(keys, contacts, strict=True)))


def _parse_cards(
    state: WalkState,
    page: browser.PageState,
    text: str,
    channels: list[extraction.Channel],
    region: str,
) -> list[extraction.Contact]:
    state.step(service.STEP_MODEL, "cards", page.url)
    system, user = prompts.cards_prompt(page.url, page.title, text)
    try:
        reply = state.client.chat_json(system, user, prompts.PURPOSE_CARDS)
    except models.ModelError as exc:
        state.step(service.STEP_MODEL, f"cards failed: {exc}", page.url)
        return []
    out: list[extraction.Contact] = []
    seen: set[str] = set()
    for item in prompts.cards_from_reply(reply):
        card = extraction.card_from_json(item)
        contact = extraction.verify_card(card, text, channels, region) if card else None
        if contact is not None and contact.name.value.casefold() not in seen:
            seen.add(contact.name.value.casefold())
            out.append(contact)
    return out


def _record(
    state: WalkState,
    source: PageSource,
    found: PageFindings,
    people: list[tuple[str, extraction.Contact]],
) -> None:
    """Local observation rows and the sink's outbox events: one transaction.

    The panel row (EVENT_CONTACT) appears once per person, when the person
    first has a verified phone or email (a card without a channel waits for
    a reveal click on the same page, see 0.4.1.1)."""
    shown: list[extraction.Contact] = []
    for key, contact in people:
        known = state.cp.entities.get(key, {})
        if key not in state.emitted and ("phone" in known or "email" in known):
            state.emitted.add(key)
            shown.append(contact)
    evidence_id = source.snapshot.evidence_id
    with storage.transaction(state.conn):
        for contact in shown:
            repository.add_observation(state.conn, state.run_id, evidence_id, source.url, contact)
        if state.sink is not None:
            state.sink.page_done(state.conn, found)
    for contact in shown:
        state.contacts += 1
        event = WalkEvent(
            service.EVENT_CONTACT, url=source.url, contact=contact, evidence_id=evidence_id
        )
        state.emit(event)
