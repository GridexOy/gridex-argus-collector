"""Who reads the person cards of a page state: the rules, then 14b for what is left.

`start` (before the next step is chosen): JSON-LD `Person` items, then cards by
rule (a name line with a phone / email of the page right below it,
`extraction.text_cards`), both verified like model cards; the same canonical text
already read on another URL gives its people again.

S6 step 6.1 (TZ_SELAIN v4.0 4.1, owner 10.10.2026): the card model is the only model
of the walk, and it is asked only when the rules read nobody on a contact page that
prints at least two personal channels - a page the rules clearly failed to read. Its
text goes in windows around those channels (not the first characters of a long page,
Ellego), one call each, one attempt, a cut-off answer keeping its complete people.
The windows are no longer spread over a thread pool: the walk chooses its next step
by rule now, so there is nothing to overlap the calls with.
"""

from __future__ import annotations

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
MIN_CHANNELS = 2  # a contact page with fewer printed channels is not a failed read


@dataclass
class PendingRead:
    text: str
    channels: list[extraction.Channel]
    region: str
    digest: str
    people: list[extraction.Contact]
    asks: list[str] = field(default_factory=list)  # windows the card model still has to read
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
    """Spans of channels that may be a person's (not a company / office channel)."""
    spans = []
    for channel in read.channels:
        span = channel.span
        if span is None or extraction.section_at(sections, span.start):
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


def _rules_failed(read: PendingRead, page: browser.PageState,
                  spans: list[tuple[int, int]]) -> bool:
    """When the rules clearly failed to read a page that holds people.

    TZ_SELAIN v4.0 4.1 proposed "a contact page with 0 people read and >= 2 printed
    channels". On the stands that threshold loses people: a team page (`fixture_oy`
    team.html) is no `contact` link by title or URL, and its people were read by the
    model before. Taken as decided - correct me if wrong: the page must print at least
    two personal channels, and be either a contact page or hold channels that belong to
    nobody yet (`spans`). Both halves still mean "the rules read nobody here"."""
    printed = [c for c in read.channels if c.kind in ("phone", "email")]
    if len(printed) < MIN_CHANNELS:
        return False
    return bool(spans) or discovery.contact_link(page.title, page.url)


def start(state: WalkState, page: browser.PageState, text: str,
          channels: list[extraction.Channel], sections: list[extraction.Section],
          region: str) -> PendingRead:
    """JSON-LD and rule cards now; the windows the card model has to read noted."""
    read = PendingRead(text, channels, region, evidence.sha256_text(text), [])
    jsonld = _verified(extraction.jsonld_people(page.html), read)
    ruled = _verified(extraction.text_cards(text, channels), read)
    read.people = jsonld + ruled
    state.timing.cards = "jsonld" if jsonld else "rules" if ruled else "skip"
    if read.digest in state.read_cache:
        state.timing.cards = "cache"
        read.people = list(state.read_cache[read.digest])
    if read.people:  # no model on this page (owner 06.10.2026); its next step: rules
        state.ruled_urls.add(discovery.normalize_url(page.url))
        return read
    spans = _unexplained(read, sections)
    if _rules_failed(read, page, spans):
        read.asks = windows(read.text, spans)
    return read


def finish(state: WalkState, page: browser.PageState, read: PendingRead
           ) -> list[extraction.Contact]:
    """Ask the card model for every window the rules left; every person verified."""
    if read.asks:
        state.step(service.STEP_MODEL, "cards", page.url)
        state.timing.cards = f"model:{state.client.config.name}"
    for part in read.asks:
        system, user = prompts.cards_prompt(page.url, page.title, part)
        try:
            reply = state.client.chat_json(system, user, prompts.PURPOSE_CARDS,
                                           salvage=prompts.salvage_people)
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
