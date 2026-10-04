"""Pure extraction logic: deterministic channels and the verbatim card check."""

from __future__ import annotations

from dataclasses import dataclass

from argus_collector.evidence.contract import TextSpan, find_span
from argus_collector.extraction import repository as reader
from argus_collector.normalization import contract as norm

KIND_EMAIL = "email"
KIND_PHONE = "phone"
CONTACT_WORDS = ("yhteystiedot", "contact", "puh", "tel", "email", "sähköposti", "@", "henkil")
LOCATOR_TEXT = "text"


@dataclass(frozen=True)
class Channel:
    kind: str  # email | phone
    value: str  # normalised (lower-case domain / E.164)
    raw: str  # as found in the page
    locator: str  # href:tel | href:mailto | jsonld:<pointer> | cfemail | text
    span: TextSpan | None


@dataclass(frozen=True)
class PersonCard:
    """One card as the model returned it; every field is raw and unverified."""

    name: str
    title: str | None = None
    phone: str | None = None
    email: str | None = None


@dataclass(frozen=True)
class VerifiedField:
    value: str  # normalised value (name/title: whitespace-normalised)
    quote: str  # exact text found on the page
    start: int  # code-point span in the canonical text, -1 when from an href only
    end: int
    locator: str  # text | href:tel | href:mailto | jsonld:<pointer> | cfemail


@dataclass(frozen=True)
class Contact:
    name: VerifiedField
    title: VerifiedField | None
    phone: VerifiedField | None
    email: VerifiedField | None


def _normalize(kind: str, raw: str, region: str = norm.DEFAULT_REGION) -> str | None:
    if kind == KIND_EMAIL:
        return norm.normalize_email(raw)
    return norm.normalize_phone(raw, region)


def _channel(
    kind: str, raw: str, locator: str, text: str, visible: str = "", region: str = "FI"
) -> Channel | None:
    value = _normalize(kind, raw, region)
    if value is None:
        return None
    span = find_span(text, visible) if visible else None
    if span is None:
        span = find_span(text, raw)
    return Channel(kind, value, visible or raw, locator, span)


def _href_channels(finds: reader.RawFinds, text: str, region: str) -> list[Channel | None]:
    out: list[Channel | None] = []
    for href, visible in finds.tel_hrefs:
        out.append(_channel(KIND_PHONE, href, "href:tel", text, visible, region))
    for href, visible in finds.mailto_hrefs:
        out.append(_channel(KIND_EMAIL, href, "href:mailto", text, visible))
    return out


def extract_channels(html: str, text: str, region: str = norm.DEFAULT_REGION) -> list[Channel]:
    finds = reader.raw_finds(html)
    found = _href_channels(finds, text, region)
    for kind, raw, pointer in reader.jsonld_channels(finds.jsonld):
        found.append(_channel(kind, raw, pointer, text, region=region))
    for encoded in finds.cfemails:
        decoded = norm.decode_cfemail(encoded)
        if decoded:
            found.append(Channel(KIND_EMAIL, decoded, encoded, "cfemail", None))
    for raw in norm.find_emails(text):
        found.append(_channel(KIND_EMAIL, raw, LOCATOR_TEXT, text))
    for raw in norm.find_phones(text, region):
        found.append(_channel(KIND_PHONE, raw, LOCATOR_TEXT, text, region=region))
    unique: dict[tuple[str, str], Channel] = {}
    for channel in found:
        if channel is not None:
            unique.setdefault((channel.kind, channel.value), channel)
    return list(unique.values())


def has_contact_signals(text: str, channels: list[Channel]) -> bool:
    lowered = text.lower()
    return bool(channels) or any(word in lowered for word in CONTACT_WORDS)


def _optional(data: dict[str, object], key: str) -> str | None:
    value = data.get(key)
    if isinstance(value, int | float) and not isinstance(value, bool):
        value = str(value)
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def card_from_json(data: object) -> PersonCard | None:
    if not isinstance(data, dict):
        return None
    typed = {str(k): v for k, v in data.items()}
    name = _optional(typed, "name")
    if name is None:
        return None
    return PersonCard(
        name=name,
        title=_optional(typed, "title"),
        phone=_optional(typed, "phone"),
        email=_optional(typed, "email"),
    )


def _text_field(raw: str | None, text: str) -> VerifiedField | None:
    if raw is None:
        return None
    span = find_span(text, raw)
    if span is None:
        return None
    return VerifiedField(norm.normalize_text(span.quote), span.quote, span.start, span.end, "text")


def _channel_field(
    kind: str, raw: str | None, text: str, channels: list[Channel], region: str
) -> VerifiedField | None:
    if raw is None:
        return None
    span = find_span(text, raw)
    value = _normalize(kind, span.quote, region) if span else None
    if span is not None and value is not None:
        return VerifiedField(value, span.quote, span.start, span.end, LOCATOR_TEXT)
    wanted = _normalize(kind, raw, region)
    for channel in channels:
        if channel.kind == kind and wanted is not None and channel.value == wanted:
            if channel.span is not None:
                s = channel.span
                return VerifiedField(channel.value, s.quote, s.start, s.end, channel.locator)
            return VerifiedField(channel.value, channel.raw, -1, -1, channel.locator)
    return None


def verify_card(
    card: PersonCard, text: str, channels: list[Channel], region: str = norm.DEFAULT_REGION
) -> Contact | None:
    if norm.normalize_name(card.name) is None:
        return None
    name = _text_field(card.name, text)
    if name is None:
        return None
    return Contact(
        name=name,
        title=_text_field(card.title, text),
        phone=_channel_field(KIND_PHONE, card.phone, text, channels, region),
        email=_channel_field(KIND_EMAIL, card.email, text, channels, region),
    )
