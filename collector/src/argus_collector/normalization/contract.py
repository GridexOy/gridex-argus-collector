"""Single entry point of the `normalization` module (pure functions).

Phones, emails, names and text whitespace are normalised here and only
here (TZ_SELAIN section 11). Original values are never thrown away by the
callers: they keep the raw quote and store the normalised value next to it.
"""

from __future__ import annotations

from argus_collector.normalization import service

__all__ = [
    "DEFAULT_REGION",
    "decode_cfemail",
    "find_emails",
    "find_phones",
    "normalize_email",
    "normalize_name",
    "normalize_phone",
    "normalize_text",
    "same_value",
]

DEFAULT_REGION = service.DEFAULT_REGION


def normalize_text(raw: str) -> str:
    """Collapse all whitespace runs to one space and strip; NFC."""
    return service.normalize_text(raw)


def normalize_name(raw: str) -> str | None:
    """Whitespace-normalised person name, None when it cannot be a name."""
    return service.normalize_name(raw)


def normalize_email(raw: str) -> str | None:
    """Decode obfuscations ((at), [at], " at ", (dot), [dot], " dot "), lower-case
    the whole address; None when the result is not an address."""
    return service.normalize_email(raw)


def normalize_phone(raw: str, region: str = DEFAULT_REGION) -> str | None:
    """E.164 (`+358401234567`) for a confident number, else None.

    Finnish rules: `0xx` -> `+358xx`, `+358`/`00358` kept, `(0)` dropped;
    an extension after `ext`/`-` is cut. Too short/long -> None.
    """
    return service.normalize_phone(raw, region)


def decode_cfemail(encoded: str) -> str | None:
    """Decode a Cloudflare `data-cfemail` hex string to the address."""
    return service.decode_cfemail(encoded)


def find_emails(text: str) -> list[str]:
    """Raw email-looking substrings in `text`, obfuscated ones included, in order."""
    return service.find_emails(text)


def find_phones(text: str) -> list[str]:
    """Raw phone-looking substrings in `text` (Finnish and international), in order."""
    return service.find_phones(text)


def same_value(kind: str, left: str, right: str) -> bool:
    """True when two raw values normalise to the same email/phone/name/text."""
    return service.same_value(kind, left, right)
