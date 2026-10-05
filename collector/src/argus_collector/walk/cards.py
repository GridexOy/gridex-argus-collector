"""Who reads the person cards of a page state (owner 05.10.2026: 14b only when needed).

1. JSON-LD `Person` items, verified against the visible text like model cards;
2. the same canonical text already read on another URL: its people again;
3. skip when nothing on the page can be a person's: no channel outside the
   generic mailboxes, switchboard lines and country-office blocks, and the
   page is not a contact / people page by its title or URL;
4. else the card model (14b); its people are added to the JSON-LD ones.
`state.timing.cards` (the `reader` of the timing line) says which one read them.
"""

from __future__ import annotations

from argus_collector.browser import contract as browser
from argus_collector.discovery import contract as discovery
from argus_collector.evidence import contract as evidence
from argus_collector.extraction import contract as extraction
from argus_collector.models import contract as models
from argus_collector.walk import prompts, service
from argus_collector.walk.state import WalkState
from argus_collector.walk.timing import timed

UNASSIGNED = "unassigned_channel"


def _verified(cards: list[extraction.PersonCard], text: str, channels: list[extraction.Channel],
              region: str, seen: set[str]) -> list[extraction.Contact]:
    out: list[extraction.Contact] = []
    for card in cards:
        contact = extraction.verify_card(card, text, channels, region)
        if contact is not None and contact.name.value.casefold() not in seen:
            seen.add(contact.name.value.casefold())
            out.append(contact)
    return out


def _personal(text: str, channels: list[extraction.Channel],
              sections: list[extraction.Section], known: set[str]) -> bool:
    """A channel that may be a person's and that no JSON-LD person explains."""
    for channel in channels:
        start = channel.span.start if channel.span is not None else -1
        if channel.value in known or extraction.section_at(sections, start) is not None:
            continue
        if extraction.classify_unattached(channel, text).entity_type == UNASSIGNED:
            return True
    return False


def _model(state: WalkState, page: browser.PageState, text: str) -> list[extraction.PersonCard]:
    state.step(service.STEP_MODEL, "cards", page.url)
    state.timing.cards = f"model:{state.client.config.name}"
    system, user = prompts.cards_prompt(page.url, page.title, text)
    try:
        reply = state.client.chat_json(system, user, prompts.PURPOSE_CARDS)
    except models.ModelError as exc:
        state.step(service.STEP_MODEL, f"cards failed: {exc}", page.url)
        return []
    cards = [extraction.card_from_json(item) for item in prompts.cards_from_reply(reply)]
    return [card for card in cards if card is not None]


def read(state: WalkState, page: browser.PageState, text: str,
         channels: list[extraction.Channel], sections: list[extraction.Section],
         region: str) -> list[extraction.Contact]:
    """The page's verified people, read by the cheapest reader that can."""
    seen: set[str] = set()
    people = _verified(extraction.jsonld_people(page.html), text, channels, region, seen)
    state.timing.cards = "jsonld" if people else "skip"
    known = {f.value for c in people for f in (c.phone, c.email) if f is not None}
    digest = evidence.sha256_text(text)
    if digest in state.read_cache:
        state.timing.cards = "cache"
        return list(state.read_cache[digest])
    contact_page = discovery.contact_link(page.title, page.url)
    if not extraction.has_contact_signals(text, channels) or not (
            _personal(text, channels, sections, known) or (contact_page and not people)):
        state.read_cache[digest] = people
        return people
    with timed(state.timing, "cards"):
        people += _verified(_model(state, page, text), text, channels, region, seen)
    state.read_cache[digest] = people
    return people
