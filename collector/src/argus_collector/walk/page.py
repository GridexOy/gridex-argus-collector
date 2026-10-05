"""One observed page: budget, snapshot, channels, model cards, findings, record."""

from __future__ import annotations

from dataclasses import dataclass

from argus_collector.browser import contract as browser
from argus_collector.discovery import contract as discovery
from argus_collector.evidence import contract as evidence
from argus_collector.extraction import contract as extraction
from argus_collector.normalization import contract as norm
from argus_collector.storage import contract as storage
from argus_collector.walk import cards, coverage, findings, repository, service, structure
from argus_collector.walk.context import PageContext
from argus_collector.walk.service import WalkEvent
from argus_collector.walk.sink import PageFindings, PageSource
from argus_collector.walk.state import WalkState
from argus_collector.walk.timing import timed

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
    frontier = [c for c in state.frontier_candidates() if not structure.foreign(state, c)]
    pool = structure.offered(state, page.candidates) + frontier
    ordered = discovery.rank_candidates(pool, set(state.cp.visited), state.hosts, state.focus)
    links = [c for c in ordered if c.kind == "link"][:MAX_LINKS_SHOWN]
    finished = discovery.normalize_url(page.url) in state.finished_urls  # finish_branch
    buttons = [c for c in ordered if c.kind == "button" and c.selector not in state.failed_targets
               and not finished]
    return links + buttons[:MAX_BUTTONS_SHOWN]


@dataclass
class Pending:
    """A new page state whose people are being read: finished before any navigation."""

    key: str
    source: PageSource
    lang: str
    sections: list[extraction.Section]
    channels: list[extraction.Channel]
    read: cards.PendingRead


def observe(
    state: WalkState, wb: browser.WalkBrowser, page: browser.PageState
) -> tuple[str, Pending | None]:
    """Snapshot a page state not seen before and start reading its people (`complete`
    finishes it before the next action); a state seen again feeds the loop detector."""
    text = evidence.canonical_text(page.text)
    key = discovery.page_key(page.url, evidence.sha256_text(text))
    offered = structure.offered(state, page.candidates)
    links = discovery.rank_candidates(offered, set(state.cp.visited), state.hosts)
    if state.job_mode:
        coverage.note_foreign_links(state, page.url, [c for c in offered if c.kind == "link"])
    state.remember_links(page.url, [c for c in links if c.kind == "link"])
    pending = None
    if key not in state.cp.seen_keys:
        state.cp.seen_keys.append(key)
        pending = _start(state, page, text, key)
    elif state.seen_again(page.url, key):
        state.step(service.STEP_LOOP, "finish_branch", page.url)
    state.cp.last_url = page.url
    state.save_checkpoint()
    return text, pending


def _learn_language(state: WalkState, lang: str) -> None:
    if not state.cp.native_language and lang:
        state.cp.native_language = lang.split("-", 1)[0].lower()[:2]
    if state.focus is not None and not state.focus.native_language and state.cp.native_language:
        state.focus = state.focus.with_native(state.cp.native_language)


def _store(state: WalkState, page: browser.PageState, text: str, key: str) -> PageSource:
    """Evidence file + `source.processed` of a new page state."""
    snapshot = evidence.store_snapshot(
        state.conn, page.url, page.url, page.html, page.text, state.settings.evidence_dir
    )
    source = PageSource(
        state.uid("source", key), state.source_id, page.url, page.url, key, snapshot, text
    )
    state.source_id = source.source_id
    if state.sink is not None:
        state.sink.page_stored(state.conn, source)
    return source


def _channels(
    state: WalkState, page: browser.PageState, text: str
) -> tuple[str, str, list[extraction.Section], list[extraction.Channel]]:
    """(html lang, phone region, country sections, channels) of a page state."""
    settings = state.settings
    lang = extraction.html_language(page.html)
    _learn_language(state, lang)
    region = norm.region_for_page(page.url, lang, settings.region_fallback)
    region = region or settings.region_fallback
    panels = [(label, evidence.canonical_text(body)) for label, body in page.tab_panels]
    sections = extraction.country_sections(text) + extraction.panel_sections(text, panels)
    channels = extraction.extract_channels(
        page.html, text, region, extraction.region_resolver(sections, region),
        frozenset(page.hidden_hrefs),
    )
    return lang, region, sections, channels


def _start(state: WalkState, page: browser.PageState, text: str, key: str) -> Pending:
    with timed(state.timing, "snapshot"):
        source = _store(state, page, text, key)
    state.step(service.STEP_EXTRACTING, "", page.url)
    with timed(state.timing, "extract"):
        lang, region, sections, channels = _channels(state, page, text)
        read = cards.start(state, page, text, channels, sections, region)
    state.page_has_contacts = bool(read.people or read.calls or channels)
    return Pending(key, source, lang, sections, channels, read)


def complete(state: WalkState, wb: browser.WalkBrowser, page: browser.PageState,
             pending: Pending | None) -> None:
    """The page's people read, bound and recorded: always before the next action."""
    if pending is None:
        return
    with timed(state.timing, "cards"):
        contacts = cards.finish(state, page, pending.read)
    state.page_has_contacts = bool(contacts or pending.channels)
    coverage.note_total(state, pending.read.text, len(contacts))
    with timed(state.timing, "bind"):
        bindings = wb.bindings(findings.probes(contacts)) if state.job_mode and contacts else []
    with timed(state.timing, "record"):
        context = PageContext(tuple(pending.sections), pending.lang)
        found, keys = findings.build_findings(state, pending.source, contacts, bindings,
                                              pending.channels, context)
        _record(state, pending.source, found, list(zip(keys, contacts, strict=True)))
    state.progress += sum(len(entity.fields) for entity in found.entities)
    state.loops[pending.key] = (0, state.progress)


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
