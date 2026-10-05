"""Person cards read from the page text without the model (owner 05.10.2026, Ellego).

Rules, then the model: a card is a name line followed within four lines by a
phone or an email the page has; the first other line between is the title.
A name line has 2-4 words, each a capitalised word (letters, `-`, `'`;
particles `von`, `af`, `de` ... in lower case), no digit, and no word of a
role, a department or an organisation (`Manager`, `Sales`, `Oy`). Cards are
verified like model cards (`verify_card`), so nothing is taken that is not on
the page.
"""

from __future__ import annotations

import bisect
import re

from argus_collector.extraction.service import KIND_EMAIL, KIND_PHONE, Channel, PersonCard

LOOKAHEAD = 4
UPPER, LOWER = "A-ZÅÄÖÜÉÈÁÍÓÚØÆ", "a-zåäöüéèáíóúßøæ"
WORD_RE = re.compile(rf"^[{UPPER}][{LOWER}]+(?:[-'][{UPPER}]?[{LOWER}]+)*$")
PARTICLES = frozenset({"von", "van", "af", "de", "da", "der", "den", "la", "le", "di", "du"})
NOT_NAME = frozenset("""
manager director sales service services engineer assistant coordinator specialist head chief
officer ceo cfo cto coo president partner owner founder representative consultant technician
controller accountant administrator administration marketing logistics finance support customer
account key project product products area export import purchasing purchase production quality
development team lead leader office department contact contacts company group spare parts
management communications operations human resources hr it legal general board member trainee
oy oyj ab gmbh ltd inc as aps kg co our us we your meet find call get touch read more see all new
home about news careers jobs privacy cookies terms imprint menu search language english suomi
svenska deutsch tel phone mobile email fax address headquarters subsidiary global worldwide
leiter vertrieb verkauf technik geschaftsfuhrer chef saljare
""".split())


def name_line(line: str) -> bool:
    words = line.split()
    if not 2 <= len(words) <= 4:
        return False
    capital = [w for w in words if w not in PARTICLES]
    if len(capital) < 2 or not all(WORD_RE.match(w) for w in capital):
        return False
    return not any(w.lower().strip("'") in NOT_NAME for w in words)


def _lines(text: str) -> tuple[list[int], list[str]]:
    starts, lines, offset = [], [], 0
    for line in text.split("\n"):
        starts.append(offset)
        lines.append(line.strip())
        offset += len(line) + 1
    return starts, lines


def _by_line(starts: list[int], channels: list[Channel]) -> dict[int, list[Channel]]:
    out: dict[int, list[Channel]] = {}
    for channel in channels:
        if channel.span is not None and channel.kind in (KIND_PHONE, KIND_EMAIL):
            out.setdefault(bisect.bisect_right(starts, channel.span.start) - 1, []).append(channel)
    return out


def _card(i: int, lines: list[str], on_line: dict[int, list[Channel]]) -> PersonCard | None:
    title: str | None = None
    phone: str | None = None
    email: str | None = None
    for j in range(i + 1, min(i + 1 + LOOKAHEAD, len(lines))):
        if name_line(lines[j]):
            break
        found = on_line.get(j, [])
        phone = phone or next((c.raw for c in found if c.kind == KIND_PHONE), None)
        email = email or next((c.raw for c in found if c.kind == KIND_EMAIL), None)
        if not found and title is None and lines[j] and phone is None and email is None:
            title = lines[j]
    if phone is None and email is None:
        return None
    return PersonCard(lines[i], title, phone, email)


def text_cards(text: str, channels: list[Channel]) -> list[PersonCard]:
    """Cards of name lines that have a channel of the page right below them."""
    starts, lines = _lines(text)
    on_line = _by_line(starts, channels)
    out: list[PersonCard] = []
    for i, line in enumerate(lines):
        if name_line(line):
            card = _card(i, lines, on_line)
            if card is not None:
                out.append(card)
    return out
