"""Reading side of extraction: the html document (hrefs, JSON-LD, cfemail).

No network and no database here; the "store" this module reads is the
snapshot html handed to it. Everything returned is raw: `service.py`
normalises and attaches locators.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any


@dataclass
class RawFinds:
    tel_hrefs: list[tuple[str, str]] = field(default_factory=list)  # (href value, link text)
    mailto_hrefs: list[tuple[str, str]] = field(default_factory=list)
    cfemails: list[str] = field(default_factory=list)
    jsonld: list[str] = field(default_factory=list)


class _Collector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.finds = RawFinds()
        self._link: tuple[str, str, list[str]] | None = None
        self._script_ld = False
        self._ld_chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {k: v or "" for k, v in attrs}
        if tag == "a":
            href = attributes.get("href", "").strip()
            lower = href.lower()
            if lower.startswith("tel:") or lower.startswith("mailto:"):
                self._link = (lower.split(":", 1)[0], href, [])
        if "data-cfemail" in attributes:
            self.finds.cfemails.append(attributes["data-cfemail"])
        if tag == "script" and attributes.get("type", "").lower() == "application/ld+json":
            self._script_ld = True
            self._ld_chunks = []

    def handle_data(self, data: str) -> None:
        if self._link is not None:
            self._link[2].append(data)
        if self._script_ld:
            self._ld_chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._link is not None:
            kind, href, chunks = self._link
            text = " ".join("".join(chunks).split())
            target = self.finds.tel_hrefs if kind == "tel" else self.finds.mailto_hrefs
            target.append((href, text))
            self._link = None
        if tag == "script" and self._script_ld:
            self.finds.jsonld.append("".join(self._ld_chunks))
            self._script_ld = False


def raw_finds(html: str) -> RawFinds:
    parser = _Collector()
    try:
        parser.feed(html)
        parser.close()
    except (AssertionError, ValueError):
        pass
    return parser.finds


def _walk_jsonld(node: Any, pointer: str, out: list[tuple[str, str, str]]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            child = f"{pointer}/{key}"
            if key in ("telephone", "email", "faxNumber") and isinstance(value, str):
                out.append(("phone" if key != "email" else "email", value, child))
            else:
                _walk_jsonld(value, child, out)
    elif isinstance(node, list):
        for i, item in enumerate(node):
            _walk_jsonld(item, f"{pointer}/{i}", out)


def jsonld_channels(blocks: list[str]) -> list[tuple[str, str, str]]:
    """(kind, raw value, json pointer) for telephone/email/faxNumber in JSON-LD blocks."""
    found: list[tuple[str, str, str]] = []
    for i, block in enumerate(blocks):
        try:
            data = json.loads(block)
        except ValueError:
            continue
        _walk_jsonld(data, f"jsonld:{i}", found)
    return found
