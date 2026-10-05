"""Who reads the person cards of a page state (owner 05.10.2026: rules, then 14b).

`start` (before the next step is chosen): JSON-LD `Person` items, then cards
by rule (a name line with a phone / email of the page right below it,
`extraction.text_cards`), both verified like model cards; the same canonical
text already read on another URL gives its people again. The card model is
asked only for what is left: a channel that may be a person's and that no
read card explains, or a contact page with nobody read. A long page goes in
windows around those channels (not the first 8000 characters, Ellego), each
window one call on a worker thread, so the next step is chosen meanwhile.
`finish` (before any navigation): the calls are joined and logged, a cut-off
answer keeps its complete people, every card is verified.
"""

from __future__ import annotations

from concurrent.futures import Future
from dataclasses import dataclass, field

from argus_collector.browser import contract as browser
from argus_collector.discovery import contract as discovery
from argus_collector.evidence import contract as evidence
from argus_collector.extraction import contract as extraction
from argus_collector.models import contract as models
from argus_collector.walk import prompts, service
from argus_collector.walk.state import WalkState

UNASSIGNED = "unassigned_channel"
BEFORE, AFTER, MAX_WINDOWS = 1500, 600, 6


@dataclass
class PendingRead:
    text: str
    channels: list[extraction.Channel]
    region: str
    digest: str
    people: list[extraction.Contact]
    calls: list[Future[models.Detached]] = field(default_factory=list)
    seen: set[str] = field(default_factory=set)


def _verified(cards: list[extraction.PersonCard], read: PendingRead) -> list[extraction.Contact]:
    out: list[extraction.Contact] = []
    for card in cards:
        contact = extraction.verify_card(card, read.text, read.channels, read.region)
        if contact is not None and contact.name.value.casefold() not in read.seen:
            read.seen.add(contact.name.value.casefold())
            out.append(contact)
    return out


def _unexplained(read: PendingRead, sections: list[extraction.Section]) -> list[tuple[int, int]]:
    """Spans of channels that may be a person's and that no read card explains."""
    known = {f.value for c in read.people for f in (c.phone, c.email) if f is not None}
    spans = []
    for channel in read.channels:
        span = channel.span
        if span is None or channel.value in known or extraction.section_at(sections, span.start):
            continue
        if extraction.classify_unattached(channel, read.text).entity_type == UNASSIGNED:
            spans.append((span.start, span.end))
    return spans


def windows(text: str, spans: list[tuple[int, int]]) -> list[str]:
    """The text for the card model: whole when short, else windows around `spans`."""
    if len(text) <= prompts.MAX_TEXT_CHARS:
        return [text]
    if not spans:
        step = prompts.MAX_TEXT_CHARS
        return [text[i:i + step] for i in range(0, len(text), step)][:MAX_WINDOWS]
    merged: list[list[int]] = []
    for start, end in sorted(spans):
        lo, hi = max(0, start - BEFORE), min(len(text), end + AFTER)
        if merged and lo <= merged[-1][1] and hi - merged[-1][0] <= prompts.MAX_TEXT_CHARS:
            merged[-1][1] = max(merged[-1][1], hi)
        else:
            merged.append([lo, hi])
    return [text[lo:hi] for lo, hi in merged][:MAX_WINDOWS]


def _ask(state: WalkState, page: browser.PageState, read: PendingRead, spans: list[tuple[int, int]]
         ) -> None:
    state.step(service.STEP_MODEL, "cards", page.url)
    state.timing.cards = f"model:{state.client.config.name}"
    for part in windows(read.text, spans):
        system, user = prompts.cards_prompt(page.url, page.title, part)
        call = (system, user, prompts.PURPOSE_CARDS)
        read.calls.append(state.submit(state.client.detached_json, *call,
                                       salvage=prompts.salvage_people))


def start(state: WalkState, page: browser.PageState, text: str,
          channels: list[extraction.Channel], sections: list[extraction.Section],
          region: str) -> PendingRead:
    """JSON-LD and rule cards now; the card model's calls started for what is left."""
    read = PendingRead(text, channels, region, evidence.sha256_text(text), [])
    jsonld = _verified(extraction.jsonld_people(page.html), read)
    ruled = _verified(extraction.text_cards(text, channels), read)
    read.people = jsonld + ruled
    state.timing.cards = "jsonld" if jsonld else "rules" if ruled else "skip"
    if read.digest in state.read_cache:
        state.timing.cards = "cache"
        read.people = list(state.read_cache[read.digest])
        return read
    spans = _unexplained(read, sections)
    contact_page = discovery.contact_link(page.title, page.url) and not read.people
    if extraction.has_contact_signals(text, channels) and (spans or contact_page):
        _ask(state, page, read, spans)
    return read


def finish(state: WalkState, page: browser.PageState, read: PendingRead
           ) -> list[extraction.Contact]:
    """Join and log the card model's calls; every person of the page, verified."""
    for call in read.calls:
        try:
            reply = state.client.record(call.result())
        except models.ModelError as exc:
            state.step(service.STEP_MODEL, f"cards failed: {exc}", page.url)
            continue
        cards = [extraction.card_from_json(item) for item in prompts.cards_from_reply(reply)]
        read.people += _verified([c for c in cards if c is not None], read)
    state.read_cache[read.digest] = read.people
    return read.people


def read(state: WalkState, page: browser.PageState, text: str,
         channels: list[extraction.Channel], sections: list[extraction.Section],
         region: str) -> list[extraction.Contact]:
    """`start` and `finish` at once (no step to choose meanwhile)."""
    return finish(state, page, start(state, page, text, channels, sections, region))
