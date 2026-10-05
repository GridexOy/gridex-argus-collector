"""Countries of labels and links, the exhibition-country seed, department order.

Owner decisions 05.10.2026: on an international contact page with a country
list only the exhibition country is opened; a seed that already is the
exhibition-country version (`.fi`, `/fi/`, `fi.` sub-domain) is walked first
and the other country versions after it; department tabs are all walked,
sales and marketing first. Pure functions over the tables in country_names.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from argus_collector.discovery import country_names as tables
from argus_collector.discovery.focus import fold

LABEL_MAX_LEN = 40
PUNCT_RE = re.compile(r"[()\[\]|/,:;.–—\-]+")
LOCALE_SEGMENT_RE = re.compile(r"^([a-z]{2})(?:[-_]([a-z]{2}))?$")
LANGUAGE_COUNTRIES = {"fi": "FI", "sv": "SE", "nb": "NO", "no": "NO", "da": "DK", "et": "EE",
                      "de": "DE", "nl": "NL", "fr": "FR", "it": "IT", "es": "ES", "pl": "PL"}
TLD_COUNTRIES = {code.lower(): code for code in tables.COUNTRY_LABELS} | {"uk": "GB"}
FOLDED_NAMES: dict[str, str] = {
    name: code for code, names in tables.COUNTRY_LABELS.items() for name in names
}


def _clean(label: str) -> str:
    words = [w for w in PUNCT_RE.sub(" ", fold(label)).split() if w not in tables.LABEL_NOISE]
    return " ".join(words)


def label_country(label: str) -> str | None:
    """Country a short label names as a whole (`Finland`, `Suomi / Finland`, `FI`)."""
    text = label.strip()
    if not text or len(text) > LABEL_MAX_LEN:
        return None
    if text in tables.COUNTRY_CODES:
        return tables.CODE_ALIASES.get(text, text)
    cleaned = _clean(text)
    if cleaned in FOLDED_NAMES:
        return FOLDED_NAMES[cleaned]
    words = cleaned.split()
    named = {FOLDED_NAMES[w] for w in words if w in FOLDED_NAMES}
    return named.pop() if len(named) == 1 and len(words) <= 3 else None


def url_country(url: str) -> str | None:
    """Country version a URL is: ccTLD, `fi.` sub-domain, `/fi-fi/` or `/fi/` path."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return None
    host = (parts.hostname or "").lower()
    labels = host.split(".")
    if len(labels) >= 2 and labels[-1] in TLD_COUNTRIES:
        return TLD_COUNTRIES[labels[-1]]
    if len(labels) >= 3 and labels[0] in tables.SUBDOMAIN_COUNTRIES:
        return tables.SUBDOMAIN_COUNTRIES[labels[0]]
    segment = parts.path.strip("/").split("/", 1)[0].lower()
    match = LOCALE_SEGMENT_RE.match(segment)
    if match is None:
        return None
    region = (match.group(2) or "").upper()
    if region and region in tables.COUNTRY_LABELS:
        return region
    return LANGUAGE_COUNTRIES.get(match.group(1)) if not match.group(2) else None


def link_country(text: str, href: str) -> str | None:
    """Country a link or control leads to: its label first, then its URL."""
    return label_country(text) or (url_country(href) if href else None)


def is_local_seed(seed_url: str, country: str) -> bool:
    """The seed already is the exhibition-country version of the site."""
    return bool(country) and url_country(seed_url) == country.upper()


def department_rank(label: str) -> int:
    """0 sales / marketing, 2 support functions, 1 everything else (business units)."""
    words = fold(label)
    if any(re.search(rf"(?<![a-z]){re.escape(w)}", words) for w in tables.DEPARTMENT_FIRST):
        return 0
    if any(re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", words)
           for w in tables.DEPARTMENT_LAST):
        return 2
    return 1
