"""An address pattern the page itself states (owner 06.10.2026, Reimax 0.4.8.6).

`Our e-mail addresses are the following: firstname.lastname@reimax.net` is not
an address (RULES K3: a pattern was once written as one) but the company's
`email_pattern`, quoted from its line. A person of the same page whose email
the page does not print gets the address the pattern gives for the name;
the walk sends it unconfirmed (ARGUS: `inferred`, oletettu) with that line as
its quote. Placeholder words in English, Finnish, Swedish, Norwegian, German,
French, Spanish and Dutch, with `.` `_` `-` or nothing between, either order.
"""

from __future__ import annotations

import re
import unicodedata
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
PART = re.compile(r"[^a-z0-9-]")


@dataclass(frozen=True)
class EmailPattern:
    value: str  # canonical form: `firstname.lastname@reimax.net`
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
    """Patterns stated in the canonical page text, in page order."""
    found: list[EmailPattern] = []
    for regex, last_first in ((FIRST_LAST, False), (LAST_FIRST, True)):
        for match in regex.finditer(text):
            sep, domain = match.group(1), match.group(2).lower().rstrip(".")
            lo, hi = _line(text, match.start(), match.end())
            words = ("lastname", "firstname") if last_first else ("firstname", "lastname")
            value = f"{words[0]}{sep}{words[1]}@{domain}"
            found.append(EmailPattern(value, sep, last_first, domain, text[lo:hi], lo, hi))
    return sorted(found, key=lambda p: p.start)


def is_template(email: str) -> bool:
    """`firstname.lastname@x.fi` and the like: a placeholder, not anyone's address."""
    local = email.split("@", 1)[0].strip("[]<>{}()")
    return bool(TEMPLATE_LOCAL.match(re.sub(r"[\[\]<>{}()]", "", local)))


def _part(word: str) -> str:
    folded = unicodedata.normalize("NFKD", word.casefold().replace("ß", "ss"))
    plain = "".join(ch for ch in folded if not unicodedata.combining(ch))
    return PART.sub("", plain.replace("æ", "ae").replace("ø", "o")).strip("-")


def address(pattern: EmailPattern, name: str) -> str | None:
    """The address the pattern gives a full name (first and last word); None for one word."""
    words = [w for w in (_part(w) for w in name.split()) if w]
    if len(words) < 2:
        return None
    first, last = words[0], words[-1]
    local = f"{last}{pattern.separator}{first}" if pattern.last_first else (
        f"{first}{pattern.separator}{last}")
    return f"{local}@{pattern.domain}"
