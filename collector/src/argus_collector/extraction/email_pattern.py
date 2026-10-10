"""An address pattern the page itself states (owner 06.10.2026, Reimax 0.4.8.6).

`Our e-mail addresses are the following: firstname.lastname@reimax.net` is not
an address (RULES K3: a pattern was once written as one) but the company's
`email_pattern`, quoted from its line. Placeholder words in English, Finnish,
Swedish, Norwegian, German, French, Spanish and Dutch, with `.` `_` `-` or
nothing between, either order.

`value` is the pattern as the page prints it (`etunimi.sukunimi@destia.fi`),
not a canonical English form: ARGUS refuses an observation whose value its
quote does not contain (contract 3.1 `value_not_in_quote`, owner 10.10.2026).
Nobody's address is derived from a pattern any more - a derived address stands
in no line of the page, so it could carry no quote that holds it; ARGUS builds
those addresses itself from this field.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

FIRST = (r"(?:first[_-]?name|first|fore[_-]?name|given[_-]?name|etunimi|vorname|f[öo]rnamn"
         r"|fornavn|pr[ée]nom|nombre|voornaam|fname)")
LAST = (r"(?:last[_-]?name|last|sur[_-]?name|family[_-]?name|sukunimi|nachname|efternamn"
        r"|ett?ernavn|nom|apellido|achternaam|lname)")
OPEN, CLOSE = r"[\[<{(]?", r"[\]>})]?"
DOMAIN = r"@([a-z0-9-]+(?:\.[a-z0-9-]+)*\.[a-z]{2,})"
FIRST_LAST = re.compile(rf"(?<![\w.]){OPEN}{FIRST}{CLOSE}([._-]?){OPEN}{LAST}{CLOSE}{DOMAIN}", re.I)
LAST_FIRST = re.compile(rf"(?<![\w.]){OPEN}{LAST}{CLOSE}([._-]?){OPEN}{FIRST}{CLOSE}{DOMAIN}", re.I)
TEMPLATE_LOCAL = re.compile(rf"^(?:{FIRST}[._-]?{LAST}|{LAST}[._-]?{FIRST})$", re.I)
MAX_QUOTE = 300


@dataclass(frozen=True)
class EmailPattern:
    value: str  # as the page prints it: `etunimi.sukunimi@destia.fi`
    separator: str
    last_first: bool  # `lastname.firstname@...`
    domain: str
    quote: str  # the line of the page that states it (text[start:end])
    start: int
    end: int


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


def find_patterns(text: str) -> list[EmailPattern]:
    """Patterns stated in the canonical page text, in page order. The value is the
    printed pattern itself, so the quote around it always contains it."""
    found: list[EmailPattern] = []
    for regex, last_first in ((FIRST_LAST, False), (LAST_FIRST, True)):
        for match in regex.finditer(text):
            sep, domain = match.group(1), match.group(2).lower().rstrip(".")
            lo, hi = _line(text, match.start(), match.end())
            value = text[match.start():match.end()].rstrip(".")
            found.append(EmailPattern(value, sep, last_first, domain, text[lo:hi], lo, hi))
    return sorted(found, key=lambda p: p.start)


def is_template(email: str) -> bool:
    """`firstname.lastname@x.fi` and the like: a placeholder, not anyone's address."""
    local = email.split("@", 1)[0].strip("[]<>{}()")
    return bool(TEMPLATE_LOCAL.match(re.sub(r"[\[\]<>{}()]", "", local)))
