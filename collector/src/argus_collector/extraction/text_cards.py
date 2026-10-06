"""Person cards read from the page text without the model (owner 05.10.2026, Ellego).

A card is a name line, at most two plain lines (the first is the title), then
the channel lines (a phone / an email the page has); a plain line after a
channel line ends the card. A name line has 2-4 capitalised words (letters,
`-`, `'`; particles `von`, `af`, `de` ... in lower case), no digit, no word of a
role, a department, an organisation or a site menu (`Manager`, `Sales`, `Oy`,
`Etusivu`), and is not a country (`United Kingdom`). No card - the model reads
the place instead - when two name-like lines come without a channel between
them (a title that reads like a name, 0.4.8.6) or when a channel of the card is
the company's (`info@`, `vaihde`, an office line, the footer of Fixture Oy).
Cards are verified like model cards (`verify_card`): nothing is taken that is
not on the page.
"""

from __future__ import annotations

import bisect
import re

from argus_collector.discovery import contract as discovery
from argus_collector.extraction import repository as tables
from argus_collector.extraction.service import KIND_EMAIL, KIND_PHONE, Channel, PersonCard

LOOKAHEAD = 5
MAX_PLAIN = 2  # lines without a channel between a name and its first channel
# a channel of the company, not of the person whose card it would close (0.4.8.6)
SWITCHBOARD = ("vaihde", "switchboard", "zentrale", "växel", "vaxel", "sentralbord",
               "asiakaspalvelu", "customer service", "kundenservice", "kundtjänst")
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
operator supervisor foreman warehouse workshop installer mechanic electrician worker driver
planner buyer designer analyst secretary receptionist advisor adviser agent expert clerk
dispatcher estimator inspector auditor architect developer programmer tester trainer associate
executive principal intern apprentice junior senior deputy vice
oy oyj ab gmbh ltd inc as aps kg co our us we your meet find call get touch read more see all new
home about news careers jobs privacy cookies terms imprint menu search language english suomi
svenska deutsch tel phone mobile email fax address headquarters subsidiary global worldwide
etusivu yhteystiedot yhteystieto tuotteet palvelut yritys ura uutiset ajankohtaista accueil
startseite start hem hjem inicio produkte leistungen unternehmen produits kontakt kontakta
impressum datenschutz
leiter vertrieb verkauf technik geschaftsfuhrer chef saljare
""".split())


def name_line(line: str) -> bool:
    words = line.split()
    if not 2 <= len(words) <= 4:
        return False
    capital = [w for w in words if w not in PARTICLES]
    if len(capital) < 2 or not all(WORD_RE.match(w) for w in capital):
        return False
    if any(w.lower().strip("'") in NOT_NAME for w in words):
        return False
    return discovery.label_country(line) is None


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


def _company(channel: Channel, line: str) -> bool:
    if channel.kind == KIND_EMAIL:
        local = re.split(r"[._+-]", channel.value.split("@", 1)[0])[0]
        return local in tables.GENERIC_LOCAL_PARTS
    low = line.lower()
    return any(word in low for word in SWITCHBOARD + tables.OFFICE_WORDS)


def _card(i: int, lines: list[str],
          on_line: dict[int, list[Channel]]) -> tuple[PersonCard | None, int]:
    """(the card of the name on line `i` or None, the last line it took)."""
    title: str | None = None
    phone: str | None = None
    email: str | None = None
    plain, last = 0, i
    for j in range(i + 1, min(i + 1 + LOOKAHEAD, len(lines))):
        found = on_line.get(j, [])
        if not found:
            if phone or email or not lines[j]:
                if phone or email:
                    break
                continue
            if name_line(lines[j]):
                return None, j - 1  # not a card; the next name line is read on its own
            plain += 1
            if plain > MAX_PLAIN:
                break
            title = title or lines[j]
            continue
        if any(_company(c, lines[j]) for c in found):
            if phone or email:
                break  # the company's line (a footer) after the person's own channel
            return None, j  # the company's channel: not a person's by rule
        phone = phone or next((c.raw for c in found if c.kind == KIND_PHONE), None)
        email = email or next((c.raw for c in found if c.kind == KIND_EMAIL), None)
        last = j
    if phone is None and email is None:
        return None, i
    return PersonCard(lines[i], title, phone, email), last


def text_cards(text: str, channels: list[Channel]) -> list[PersonCard]:
    """Cards of name lines that have a channel of the page right below them."""
    starts, lines = _lines(text)
    on_line = _by_line(starts, channels)
    out: list[PersonCard] = []
    skip_to = -1
    for i, line in enumerate(lines):
        if i <= skip_to or not name_line(line):
            continue
        card, skip_to = _card(i, lines, on_line)
        if card is not None:
            out.append(card)
    return out
