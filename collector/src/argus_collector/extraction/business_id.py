"""The company's registration number printed on its own pages (K14, TZ v4.0 4.2 p. 8).

A Finnish Y-tunnus is seven digits, a hyphen and a check digit (`1234567-8`); the
same number appears as a VAT id `FI12345678`. Both are accepted only when the check
digit is right, so a phone number or an order code never passes for one. The number
is reported as the company's `business_id` with the line that states it as its quote,
which is also what lets ARGUS match the company against PRH.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

WEIGHTS = (7, 9, 10, 5, 8, 4, 2)
MAX_QUOTE = 300
LABELS = ("y-tunnus", "ytunnus", "fo-nummer", "fo-nr", "business id", "business-id",
          "vat", "alv", "momsnummer", "organisationsnummer", "org.nr", "ust-idnr")
NUMBER = re.compile(r"(?<![\d-])(\d{7})-(\d)(?![\d-])")
VAT = re.compile(r"(?<![A-Z0-9])FI\s?(\d{8})(?![\d])", re.I)


@dataclass(frozen=True)
class BusinessId:
    value: str  # canonical `1234567-8`, the form PRH uses
    quote: str  # the line of the page that states it
    start: int
    end: int


def check_digit(body: str) -> int | None:
    """The check digit of seven digits, or None when the number can have none."""
    total = sum(w * int(d) for w, d in zip(WEIGHTS, body, strict=True))
    rest = total % 11
    if rest == 1:
        return None
    return 0 if rest == 0 else 11 - rest


def is_valid(value: str) -> bool:
    body, _, check = value.partition("-")
    if len(body) != 7 or not body.isdigit() or not check.isdigit():
        return False
    return check_digit(body) == int(check)


def _line(text: str, start: int, end: int) -> tuple[int, int]:
    lo = text.rfind("\n", 0, start) + 1
    hi = text.find("\n", end)
    hi = len(text) if hi < 0 else hi
    if hi - lo > MAX_QUOTE:
        lo, hi = max(lo, start - MAX_QUOTE // 2), min(hi, end + MAX_QUOTE // 2)
    while lo < start and text[lo].isspace():
        lo += 1
    while hi > end and text[hi - 1].isspace():
        hi -= 1
    return lo, hi


def _labelled(text: str, start: int) -> bool:
    """A number counts when its own line (or the line above) names what it is."""
    lo = text.rfind("\n", 0, text.rfind("\n", 0, start) + 1 - 1) + 1
    return any(label in text[lo:start + 12].casefold() for label in LABELS)


def find(text: str) -> BusinessId | None:
    """The first valid business id the page states, with its line; None without one."""
    for match in NUMBER.finditer(text):
        value = f"{match.group(1)}-{match.group(2)}"
        if is_valid(value) and _labelled(text, match.start()):
            lo, hi = _line(text, match.start(), match.end())
            return BusinessId(value, text[lo:hi], lo, hi)
    for match in VAT.finditer(text):
        digits = match.group(1)
        value = f"{digits[:7]}-{digits[7]}"
        if is_valid(value):
            lo, hi = _line(text, match.start(), match.end())
            return BusinessId(value, text[lo:hi], lo, hi)
    return None
