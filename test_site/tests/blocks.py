"""Test helpers: element blocks of a fixture page and E.164 of a local number.

`blocks(html)` returns every div/button/option/select with its attributes,
its whole text, the last `<h3>` seen before it opened (`heading`) and the
ids of the divs around it (`parents`), so a test can say "this card sits in
panel p-hallinto under the heading Johto" without a browser. `page_text(html)`
is the text a reader sees, one line per block element, for "what comes first".
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser

TRACKED = ("div", "button", "select", "option")
BREAKS = {"br", "p", "div", "li", "h1", "h2", "h3", "h4", "section"}  # line breaks in innerText
UNSEEN = {"head", "script", "style", "template"}  # never part of innerText
CALLING = {
    "AT": "43", "BE": "32", "DK": "45", "FI": "358", "FR": "33", "DE": "49",
    "IT": "39", "NO": "47", "PL": "48", "SE": "46", "GB": "44", "NL": "31", "ES": "34",
    "CH": "41", "BR": "55", "CA": "1", "US": "1", "CN": "86", "IN": "91", "JP": "81",
}  # fmt: skip
NO_TRUNK_PREFIX = {"DK", "IT", "NO", "PL", "ES"}  # the leading digit stays (Italy) or is no 0


@dataclass
class Block:
    tag: str
    attrs: dict[str, str]
    heading: str
    parents: list[str]
    parts: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join("".join(self.parts).split())

    @property
    def classes(self) -> list[str]:
        return self.attrs.get("class", "").split()


class _Parser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.found: list[Block] = []
        self.open: list[Block] = []
        self.heading_parts: list[str] | None = None
        self.heading = ""

    def _break(self, tag: str) -> None:
        if tag in BREAKS:
            for block in self.open:
                block.parts.append(" ")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._break(tag)
        if tag == "h3":
            self.heading_parts = []
        if tag in TRACKED:
            parents = [b.attrs.get("id", "") for b in self.open if b.tag == "div"]
            block = Block(tag, {k: v or "" for k, v in attrs}, self.heading, parents)
            self.open.append(block)
            self.found.append(block)

    def handle_endtag(self, tag: str) -> None:
        self._break(tag)
        if tag == "h3" and self.heading_parts is not None:
            self.heading = " ".join("".join(self.heading_parts).split())
            self.heading_parts = None
        if tag in TRACKED:
            for index in range(len(self.open) - 1, -1, -1):
                if self.open[index].tag == tag:
                    del self.open[index:]
                    break

    def handle_data(self, data: str) -> None:
        if self.heading_parts is not None:
            self.heading_parts.append(data)
        for block in self.open:
            block.parts.append(data)


def blocks(html: str) -> list[Block]:
    parser = _Parser()
    parser.feed(html)
    parser.close()
    return parser.found


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.unseen = 0

    def _mark(self, tag: str, step: int) -> None:
        if tag in UNSEEN:
            self.unseen += step
        if tag in BREAKS:
            self.parts.append("\n")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._mark(tag, 1)

    def handle_endtag(self, tag: str) -> None:
        self._mark(tag, -1)

    def handle_data(self, data: str) -> None:
        if not self.unseen:  # a line break in the source is only a space
            self.parts.append(re.sub(r"\s+", " ", data))


def page_text(html: str) -> str:
    """Visible text of a page or fragment, close to `document.body.innerText`.

    One line per block element, whitespace inside a line collapsed, empty lines
    dropped; `<head>`, scripts and styles are left out. CSS and the `hidden`
    attribute are not applied, so it is the text of a page with nothing hidden.
    """
    parser = _Text()
    parser.feed(html)
    parser.close()
    lines = (" ".join(line.split()) for line in "".join(parser.parts).splitlines())
    return "\n".join(line for line in lines if line)


def by_id(found: list[Block], element_id: str) -> Block:
    return next(b for b in found if b.attrs.get("id") == element_id)


def e164(text: str, country: str) -> str:
    """Number as shown on the page -> E.164 (`+49 5246 000-0` as is; fixture countries only)."""
    digits = re.sub(r"\D", "", text)
    if text.strip().startswith("+"):
        return f"+{digits}"
    if country not in NO_TRUNK_PREFIX:
        digits = digits.removeprefix("0")
    return f"+{CALLING[country]}{digits}"
