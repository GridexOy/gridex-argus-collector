"""Single entry point of the `extraction` module.

Two jobs: (1) deterministic channels from a page (`tel:`/`mailto:` hrefs,
JSON-LD, Cloudflare `data-cfemail`, obfuscated addresses and phones in the
visible text); (2) the verbatim check of person cards the model returned:
a field survives only when its quote is found in the canonical page text
(or, for a phone/email, when it normalises to a channel found in the html).
Anything else is dropped. Nothing here depends on `models` (TZ section 11).
"""

from __future__ import annotations

from argus_collector.extraction import service
from argus_collector.extraction.service import (
    Channel,
    Contact,
    PersonCard,
    VerifiedField,
)

__all__ = [
    "Channel",
    "Contact",
    "PersonCard",
    "VerifiedField",
    "card_from_json",
    "extract_channels",
    "has_contact_signals",
    "verify_card",
]


def extract_channels(html: str, text: str) -> list[Channel]:
    """Phones and emails found deterministically; `text` is the canonical page text.

    Each channel carries the normalised `value`, the `raw` form, a `locator`
    (`href:tel`, `href:mailto`, `jsonld:<pointer>`, `cfemail`, `text`) and a
    `TextSpan` when the raw form is visible in `text`. De-duplicated by value.
    """
    return service.extract_channels(html, text)


def has_contact_signals(text: str, channels: list[Channel]) -> bool:
    """True when the page is worth a model card parse (channels or contact words)."""
    return service.has_contact_signals(text, channels)


def card_from_json(data: object) -> PersonCard | None:
    """A PersonCard from one model JSON object (`name`, `title`, `phone`, `email`)."""
    return service.card_from_json(data)


def verify_card(card: PersonCard, text: str, channels: list[Channel]) -> Contact | None:
    """Verbatim check of one model card against the canonical page text.

    - `name`: required; must be found in `text` (whitespace-insensitive).
    - `title`: kept only when found in `text`, else None.
    - `phone` / `email`: the quote found in `text` and normalising to a value,
      or a value equal to a channel from `channels` (quote = channel.raw).
    Returns None when the name is missing or not on the page.
    """
    return service.verify_card(card, text, channels)
