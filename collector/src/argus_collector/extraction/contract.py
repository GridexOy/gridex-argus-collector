"""Single entry point of the `extraction` module.

Two jobs: (1) deterministic channels from a page (`tel:`/`mailto:` hrefs,
JSON-LD, Cloudflare `data-cfemail`, obfuscated addresses and phones in the
visible text); (2) the verbatim check of person cards the model returned:
a field survives only when its quote is found in the canonical page text
(or, for a phone/email, when it normalises to a channel found in the html).
Anything else is dropped. Nothing here depends on `models` (TZ section 11).
"""

from __future__ import annotations

from collections.abc import Callable

from argus_collector.extraction import repository, roles, sections, service
from argus_collector.extraction.roles import ChannelRole
from argus_collector.extraction.sections import OfficeLines, Section
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
    "OfficeLines",
    "PersonCard",
    "Section",
    "VerifiedField",
    "card_from_json",
    "classify_unattached",
    "country_sections",
    "extract_channels",
    "has_contact_signals",
    "html_language",
    "office_lines",
    "region_resolver",
    "section_at",
    "verify_card",
]


def extract_channels(
    html: str,
    text: str,
    region: str = DEFAULT_REGION,
    region_at: Callable[[int], str] | None = None,
) -> list[Channel]:
    """Phones and emails found deterministically; `text` is the canonical page text.

    Each channel carries the normalised `value`, the `raw` form, a `locator`
    (`href:tel`, `href:mailto`, `jsonld:<pointer>`, `cfemail`, `text`) and a
    `TextSpan` when the raw form is visible in `text`. De-duplicated by value.
    National phone numbers are read in `region` (`normalization.region_for_page`),
    or per text offset by `region_at` (country sections). A number labelled as a
    fax is not a channel.
    """
    return service.extract_channels(html, text, region, region_at)


def country_sections(text: str) -> list[Section]:
    """Country sections of a page that names >= 3 countries on lines of their own."""
    return sections.country_sections(text)


def section_at(found: list[Section], offset: int) -> Section | None:
    return sections.section_at(found, offset)


def region_resolver(found: list[Section], default: str) -> Callable[[int], str]:
    """Phone region per text offset: the section's country, else `default`."""
    return sections.region_resolver(found, default)


def office_lines(text: str, section: Section) -> OfficeLines:
    """Company name line and address lines of an office section (spans in `text`)."""
    return sections.office_lines(text, section)


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
