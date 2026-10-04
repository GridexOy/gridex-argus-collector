"""Single entry point of the `extraction` module.

Two jobs: (1) deterministic channels from a page (`tel:`/`mailto:` hrefs,
JSON-LD, Cloudflare `data-cfemail`, obfuscated addresses and phones in the
visible text); (2) the verbatim check of person cards the model returned:
a field survives only when its quote is found in the canonical page text
(or, for a phone/email, when it normalises to a channel found in the html).
Anything else is dropped. Nothing here depends on `models` (TZ section 11).
"""

from __future__ import annotations

from argus_collector.extraction import repository, roles, service
from argus_collector.extraction.roles import ChannelRole
from argus_collector.extraction.service import (
    Channel,
    Contact,
    PersonCard,
    VerifiedField,
)
from argus_collector.normalization.contract import DEFAULT_REGION

__all__ = [
    "Channel",
    "ChannelRole",
    "Contact",
    "PersonCard",
    "VerifiedField",
    "card_from_json",
    "classify_unattached",
    "extract_channels",
    "has_contact_signals",
    "html_language",
    "verify_card",
]


def extract_channels(html: str, text: str, region: str = DEFAULT_REGION) -> list[Channel]:
    """Phones and emails found deterministically; `text` is the canonical page text.

    Each channel carries the normalised `value`, the `raw` form, a `locator`
    (`href:tel`, `href:mailto`, `jsonld:<pointer>`, `cfemail`, `text`) and a
    `TextSpan` when the raw form is visible in `text`. De-duplicated by value.
    National phone numbers are read in `region` (`normalization.region_for_page`).
    """
    return service.extract_channels(html, text, region)


def has_contact_signals(text: str, channels: list[Channel]) -> bool:
    """True when the page is worth a model card parse (channels or contact words)."""
    return service.has_contact_signals(text, channels)


def card_from_json(data: object) -> PersonCard | None:
    """A PersonCard from one model JSON object (`name`, `title`, `phone`, `email`)."""
    return service.card_from_json(data)


def verify_card(
    card: PersonCard, text: str, channels: list[Channel], region: str = DEFAULT_REGION
) -> Contact | None:
    """Verbatim check of one model card against the canonical page text.

    - `name`: required; must be found in `text` (whitespace-insensitive).
    - `title`: kept only when found in `text`, else None.
    - `phone` / `email`: the quote found in `text` and normalising to a value,
      or a value equal to a channel from `channels` (quote = channel.raw).
    Returns None when the name is missing or not on the page.
    """
    return service.verify_card(card, text, channels, region)


def classify_unattached(channel: Channel, text: str) -> ChannelRole:
    """`organization_channel` (generic mailbox, switchboard line, JSON-LD), `office`
    (its line names an office) or `unassigned_channel`, with the binding to send."""
    return roles.classify_unattached(channel, text)


def html_language(html: str) -> str:
    """`<html lang>` of a snapshot (`de`, `fi-FI`); "" when the page names none."""
    return repository.html_language(html)
