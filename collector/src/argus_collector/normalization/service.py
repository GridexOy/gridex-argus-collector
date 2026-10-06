"""Pure normalisation rules: whitespace, names, emails, phones, obfuscations."""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlsplit

from argus_collector.normalization import repository as tables

DEFAULT_REGION = "FI"


def normalize_text(raw: str) -> str:
    return tables.WHITESPACE.sub(" ", unicodedata.normalize("NFC", raw)).strip()


def normalize_name(raw: str) -> str | None:
    text = normalize_text(raw)
    if not text or len(text) > tables.NAME_MAX_LEN or tables.NAME_BAD_RE.search(text):
        return None
    if not any(ch.isalpha() for ch in text):
        return None
    return text


def _deobfuscate(raw: str) -> str:
    text = normalize_text(raw)
    text = re.sub(tables.AT_PATTERN, "@", text, flags=re.IGNORECASE)
    text = re.sub(tables.DOT_PATTERN, ".", text, flags=re.IGNORECASE)
    return text.replace(" ", "")


def normalize_email(raw: str) -> str | None:
    candidate = _deobfuscate(raw).strip(".,;:<>()[]\"'")
    if candidate.lower().startswith("mailto:"):
        candidate = candidate[7:]
    candidate = candidate.split("?", 1)[0]
    if not tables.EMAIL_VALID_RE.match(candidate):
        return None
    return candidate.lower()


def _strip_extension(raw: str) -> str:
    return tables.EXTENSION_RE.sub("", raw).strip()


def normalize_phone(raw: str, region: str = DEFAULT_REGION) -> str | None:
    text = _strip_extension(normalize_text(raw))
    if text.lower().startswith("tel:"):
        text = text[4:]
    text = text.replace("(0)", "")
    digits = tables.NON_DIGITS.sub("", text)
    if not digits:
        return None
    if text.lstrip().startswith("+"):
        national = digits
    elif digits.startswith("00"):
        national = digits[2:]
    elif digits.startswith("0"):
        code = tables.REGION_CODES.get(region.upper())
        if code is None:
            return None
        national = code + digits[1:]
    else:
        return None
    if not tables.MIN_DIGITS <= len(national) <= tables.MAX_DIGITS:
        return None
    return "+" + national


def phone_country(e164: str) -> str | None:
    """Country of an E.164 number by its calling code (`+358...` FI); None: not known."""
    if not e164.startswith("+"):
        return None
    digits = e164[1:]
    codes = sorted(tables.REGION_CODES.items(), key=lambda item: -len(item[1]))
    return next((region for region, code in codes if digits.startswith(code)), None)


def decode_cfemail(encoded: str) -> str | None:
    try:
        data = bytes.fromhex(encoded.strip())
    except ValueError:
        return None
    if len(data) < 2:
        return None
    key = data[0]
    decoded = bytes(b ^ key for b in data[1:]).decode("utf-8", errors="replace")
    return normalize_email(decoded)


def find_emails(text: str) -> list[str]:
    return [m.group(0) for m in tables.EMAIL_FIND_RE.finditer(text)]


def find_phones(text: str, region: str = DEFAULT_REGION) -> list[str]:
    found: list[str] = []
    for match in tables.PHONE_FIND_RE.finditer(text):
        raw = match.group(0).strip()
        if normalize_phone(raw, region) is not None:
            found.append(raw)
    return found


def _locale_region(tag: str) -> str | None:
    """`de-DE`/`fi_fi` -> its region; a bare language -> None (handled by the caller)."""
    match = tables.LOCALE_RE.match(tag.strip())
    if match is None or match.group(2) is None:
        return None
    region = match.group(2).upper()
    return region if region in tables.REGION_CODES else None


def _language_region(tag: str) -> str | None:
    match = tables.LOCALE_RE.match(tag.strip())
    return tables.LANGUAGE_REGIONS.get(match.group(1).lower()) if match else None


def region_for_page(url: str, html_lang: str, fallback: str | None) -> str | None:
    """National phone context of a page: ccTLD, then the region of `<html lang>`,
    then a locale path segment (`/fi/`, `/de-de/`), then the page language,
    then `fallback` (the exhibition country of the job, FI for a manual walk)."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return fallback
    host = (parts.hostname or "").lower()
    tld = host.rsplit(".", 1)[-1] if "." in host else ""
    segment = parts.path.strip("/").split("/", 1)[0]
    for found in (
        tables.TLD_REGIONS.get(tld),
        _locale_region(html_lang),
        _locale_region(segment) or _language_region(segment),
        _language_region(html_lang),
    ):
        if found is not None:
            return found
    return fallback


def same_value(kind: str, left: str, right: str) -> bool:
    if kind == "email":
        return normalize_email(left) is not None and normalize_email(left) == normalize_email(right)
    if kind == "phone":
        return normalize_phone(left) is not None and normalize_phone(left) == normalize_phone(right)
    return normalize_text(left).casefold() == normalize_text(right).casefold()
