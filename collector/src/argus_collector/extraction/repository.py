"""Reading side of extraction: the html document (hrefs, JSON-LD, cfemail).

No network and no database here; the "store" this module reads is the
snapshot html handed to it. Everything returned is raw: `service.py`
normalises and attaches locators.
"""

from __future__ import annotations

import json
import re
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


JSONLD_KINDS = {"telephone": "phone", "email": "email", "faxNumber": "fax"}


def _walk_jsonld(node: Any, pointer: str, out: list[tuple[str, str, str]]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            child = f"{pointer}/{key}"
            if key in JSONLD_KINDS and isinstance(value, str):
                out.append((JSONLD_KINDS[key], value, child))
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


HTML_LANG_RE = re.compile(
    r"<html\b[^>]*\blang\s*=\s*[\"']?([A-Za-z]{2,3}(?:[-_][A-Za-z]{2})?)", re.IGNORECASE
)

# An email whose local part starts with one of these is the company's, not a person's.
GENERIC_LOCAL_PARTS: frozenset[str] = frozenset(
    """info sales myynti office contact contacts kontakt asiakaspalvelu support tuki service
    huolto orders order tilaukset invoice invoices laskutus hr rekry careers press media
    marketing markkinointi export vienti mail post posti hello hei admin reception vaihde
    customer customerservice webmaster noreply feedback palaute shop verkkokauppa tarjous
    quote quotes purchasing hankinta osto finance talous accounting kirjanpito vertrieb
    zentrale kundenservice kundservice""".split()
)
# A line naming a switchboard / general number makes its phone the company's.
ORGANIZATION_PHONE_WORDS = (
    "vaihde", "switchboard", "zentrale", "växel", "vaxel", "sentralbord", "central",
    "asiakaspalvelu", "customer service", "kundenservice", "kundtjänst", "puh", "tel",
    "phone", "puhelin", "telefon",
)
# A line naming an office / branch makes its channel an `office` entity.
OFFICE_WORDS = ("office", "toimisto", "kontor", "niederlassung", "branch", "sivuliike")


def html_language(html: str) -> str:
    """The `lang` attribute of the `<html>` element, "" when absent."""
    match = HTML_LANG_RE.search(html[:20000])
    return match.group(1) if match else ""

# A number labelled as a fax is not a phone channel (owner 05.10.2026: no fax).
FAX_WORDS = ("fax", "faksi", "telefax", "telefaksi", "telefaks")
PHONE_LABEL_WORDS = ("puh", "puhelin", "tel", "phone", "vaihde", "switchboard", "gsm",
                     "mobile", "matkapuhelin", "telefon", "vaxel", "växel", "mob")
# Lines of an office block that name the company, not its address.
LEGAL_FORMS = ("oy", "oyj", "ab", "gmbh", "ag", "ltd", "limited", "inc", "as", "a/s", "aps",
               "sa", "s.a.", "srl", "spa", "s.p.a.", "bv", "b.v.", "nv", "sp. z o.o.", "kft")
# `00100 Helsinki`, `80939 Munchen`, `SE-111 22 Stockholm`, `SW1A 1AA London`.
POSTAL_LINE_RE = re.compile(
    r"^(?:[A-Z]{1,2}-?)?\d{3}\s?\d{2}\s+\D{2,}|^\d{4,5}\s+\D{2,}|^[A-Z]{1,2}\d[\dA-Z]?\s\d[A-Z]{2}\b"
)
STREET_LINE_RE = re.compile(r"^\D{3,}\s\d+[a-zA-Z]?(?:[\s,-].{0,20})?$")
URL_LINE_RE = re.compile(r"^(?:https?://|www\.)\S+$|^\S+\.[a-z]{2,}/\S*$", re.IGNORECASE)
