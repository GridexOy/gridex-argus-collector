"""Country sections of a page and the office blocks in them (owner 05.10.2026).

On an international contact page the visible text lists countries; under the
opened country are its local office lines: company name, street, postal
code + city, switchboard, fax, general email, a link to the local site. A
section starts at a line that is only a country name and ends at the next
such line; sections are used only when the page names >= 3 countries (a
language menu with one `Suomi` does not turn a German page Finnish). A
phone in a section is read in that section's country (`09-7422 3300` under
Finland is +358 9 7422 3300). Fax numbers are recognised and left out.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from argus_collector.discovery import contract as discovery
from argus_collector.evidence.contract import TextSpan, sha256_text
from argus_collector.extraction import repository as tables

SECTION_MIN_COUNTRIES = 3
LINE_RE = re.compile(r"[^\n]+")
WORD_RE = re.compile(r"[a-zäöå]+")


@dataclass(frozen=True)
class Section:
    country: str
    heading: TextSpan
    start: int  # content: after the heading line
    end: int  # up to the next country heading or the end of the text


@dataclass(frozen=True)
class OfficeLines:
    section: Section
    name: TextSpan | None
    address: TextSpan | None


def _lines(text: str) -> list[tuple[int, int, str]]:
    return [(m.start(), m.end(), m.group(0)) for m in LINE_RE.finditer(text)]


def _span(text: str, start: int, end: int) -> TextSpan:
    return TextSpan(start, end, text[start:end], sha256_text(text))


def country_sections(text: str) -> list[Section]:
    """Sections with content, in page order; [] when fewer than 3 countries are named."""
    heads: list[tuple[int, int, str]] = []
    for start, _end, line in _lines(text):
        stripped = line.strip()
        code = discovery.label_country(stripped) if stripped else None
        if code is not None:
            lead = len(line) - len(line.lstrip())
            heads.append((start + lead, start + lead + len(stripped), code))
    if len({code for _, _, code in heads}) < SECTION_MIN_COUNTRIES:
        return []
    out: list[Section] = []
    for i, (start, end, code) in enumerate(heads):
        stop = heads[i + 1][0] if i + 1 < len(heads) else len(text)
        if text[end:stop].strip():
            out.append(Section(code, _span(text, start, end), end, stop))
    return out


def _panel_span(text: str, panel: str) -> tuple[int, int] | None:
    """Where a panel's text is in the page text: whole, else first to last line."""
    lines = [line.strip() for line in panel.splitlines() if line.strip()]
    if not lines:
        return None
    first = text.find(lines[0])
    if first < 0:
        return None
    last = text.find(lines[-1], first)
    return (first, last + len(lines[-1])) if last >= 0 else None


def panel_sections(text: str, panels: list[tuple[str, str]]) -> list[Section]:
    """A selected tab labelled with a country (`Germany`) makes its panel that country's
    section; the heading quote is the tab label in the page text (0.4.8.0)."""
    out: list[Section] = []
    for label, panel in panels:
        code = discovery.label_country(label)
        span = _panel_span(text, panel) if code else None
        if code is None or span is None:
            continue
        head = text.rfind(label.strip(), 0, span[0])
        head = head if head >= 0 else text.find(label.strip())
        if head < 0:
            continue
        out.append(Section(code, _span(text, head, head + len(label.strip())), span[0], span[1]))
    return out


def section_at(sections: list[Section], offset: int) -> Section | None:
    for section in sections:
        if section.start <= offset < section.end:
            return section
    return None


def region_resolver(sections: list[Section], default: str) -> Callable[[int], str]:
    """Phone region of a text offset: its section's country, else the page region."""

    def region(offset: int) -> str:
        found = section_at(sections, offset) if offset >= 0 else None
        return found.country if found else default

    return region


def is_fax(text: str, start: int) -> bool:
    """The label nearest before the number on its line (or the line above) is a fax word."""
    if start < 0:
        return False
    line_start = text.rfind("\n", 0, start) + 1
    prefix = text[line_start:start].lower()
    if not prefix.strip():
        above = text.rfind("\n", 0, max(0, line_start - 1)) + 1
        prefix = text[above:line_start].lower()
    words = WORD_RE.findall(prefix)
    for word in reversed(words):
        if word in tables.FAX_WORDS:
            return True
        if word in tables.PHONE_LABEL_WORDS:
            return False
    return False


def _is_name(line: str) -> bool:
    words = {w.strip(",") for w in line.lower().split()}
    return any(form in words for form in tables.LEGAL_FORMS)


def _is_address(line: str) -> bool:
    words = set(WORD_RE.findall(line.lower()))
    if "@" in line or tables.URL_LINE_RE.match(line) or sum(c.isdigit() for c in line) >= 7:
        return False
    if words & (set(tables.FAX_WORDS) | set(tables.PHONE_LABEL_WORDS)):
        return False
    return bool(tables.POSTAL_LINE_RE.match(line) or tables.STREET_LINE_RE.match(line))


def office_lines(text: str, section: Section) -> OfficeLines:
    """Company name line and the consecutive address lines of one section."""
    name: TextSpan | None = None
    first = last = -1
    for start, end, line in _lines(text[section.start : section.end]):
        a, b = section.start + start, section.start + end
        stripped = line.strip()
        if name is None and first < 0 and _is_name(stripped):
            name = _span(text, a + len(line) - len(line.lstrip()), b)
        elif _is_address(stripped) and (first < 0 or last >= 0 and a <= last + 2):
            first = a if first < 0 else first
            last = b
        elif first >= 0:
            break
    address = _span(text, first, last) if first >= 0 else None
    return OfficeLines(section, name, address)
