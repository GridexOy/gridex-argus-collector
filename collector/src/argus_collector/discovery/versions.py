"""Country versions of a site (owner 06.10.2026: Carlo Gavazzi went to /en-br/).

`page_country` says which country's version a page is (None: a global one). The
candidates for the exhibition country's version come in the owner's order: the
page's `hreflang` alternates, its country / language switcher links, the same path
under `/fi/`, `/en-fi/`, `/fi-fi/` (only on a site with locale paths), a page named
Finland / Suomi / Nordic; a foreign version's last resort is the global one.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlsplit, urlunsplit

from argus_collector.discovery import countries
from argus_collector.discovery.focus import fold
from argus_collector.discovery.service import Candidate

LINK_TAG_RE = re.compile(r"<link\b[^>]*>", re.IGNORECASE)
ATTR_RE = re.compile(r"([a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s\"'>]+)")
LANG_RE = re.compile(r"^([a-z]{2,3})(?:[-_]([a-z]{2}))?(?![a-z])", re.IGNORECASE)
NATIVE = {code: lang for lang, code in countries.LANGUAGE_COUNTRIES.items()} | {"FI": "fi"}
REGION_WORDS = ("finland", "suomi", "nordic", "nordics", "pohjoismaat", "norden",
                "scandinavia", "skandinavia")
GLOBAL_LANGS = ("x-default", "en", "en-int", "en-gb", "en-us")


def alternates(html: str, base: str) -> list[tuple[str, str]]:
    """(hreflang, absolute href) of the page's `<link rel="alternate" hreflang>` tags."""
    out: list[tuple[str, str]] = []
    for tag in LINK_TAG_RE.findall(html):
        attrs = {k.lower(): v.strip("\"'") for k, v in ATTR_RE.findall(tag)}
        rel = attrs.get("rel", "").lower().split()
        if "alternate" in rel and attrs.get("hreflang") and attrs.get("href"):
            out.append((attrs["hreflang"].lower(), urljoin(base, attrs["href"])))
    return out


def lang_country(tag: str) -> str | None:
    """Country a language tag names: `pt-BR` BR, `fi` FI, `ru` RU; English: none."""
    match = LANG_RE.match(tag.strip())
    if match is None:
        return None
    region = (match.group(2) or "").upper()
    if region:
        return region if region in countries.TLD_COUNTRIES.values() else None
    lang = match.group(1).lower()
    return None if lang == "en" else countries.LANGUAGE_COUNTRIES.get(lang, lang.upper())


def page_country(url: str, html_lang: str) -> str | None:
    """The country version a page is: its URL (ccTLD, `fi.`, `/fi-fi/`), else `<html lang>`."""
    return countries.url_country(url) or lang_country(html_lang)


def label(url: str) -> str:
    """What the panel calls a version: its locale path (`en-br`), else its host."""
    return countries.locale_segment(url) or urlsplit(url).hostname or url


def constructed(url: str, country: str, languages: list[str]) -> list[str]:
    """`/en-br/x` -> `/fi/x`, `/en-fi/x`, `/fi-fi/x`: only a URL with a locale segment."""
    parts = urlsplit(url)
    segment = countries.locale_segment(url)
    if not segment:
        return []
    rest = parts.path.lstrip("/").split("/", 1)[1:] or [""]
    native, cc = NATIVE.get(country, country.lower()), country.lower()
    wanted = [native, f"en-{cc}", f"{native}-{cc}"] + [f"{lang}-{cc}" for lang in languages]
    paths = [f"/{seg}/{rest[0]}" for seg in dict.fromkeys(wanted) if seg != segment]
    return [urlunsplit((parts.scheme, parts.netloc, p, "", "")) for p in paths]


def declared(html: str, base: str, country: str) -> list[str]:
    """hreflang alternates of `country`: a region tag first (`fi-fi`, `en-fi`), then `fi`."""
    alts = alternates(html, base)
    region = [href for tag, href in alts if tag.endswith(f"-{country.lower()}")]
    native = [href for tag, href in alts if tag == NATIVE.get(country, "")]
    return list(dict.fromkeys(region + native))


def switchers(links: list[Candidate], country: str) -> list[str]:
    """Links whose label or locale path is the country (`Suomi`, `Finland`, `/en-fi/`)."""
    return [c.href for c in links if c.href and countries.link_country(c.text, c.href) == country]


def region_pages(links: list[Candidate]) -> list[str]:
    """Links that name Finland, Suomi or the Nordics in a longer label (`Nordic office`)."""
    def named(text: str) -> bool:
        words = re.findall(r"[a-z]+", fold(text))
        return any(w in REGION_WORDS for w in words)
    return [c.href for c in links if c.href and named(c.text)]


def global_version(html: str, base: str, url: str) -> list[str]:
    """The site's global version: hreflang `x-default` / `en`, else `/en/` of the same path."""
    alts = dict(alternates(html, base))
    found = [alts[tag] for tag in GLOBAL_LANGS if tag in alts]
    segment = countries.locale_segment(url)
    if segment and not found:
        parts = urlsplit(url)
        rest = parts.path.lstrip("/").split("/", 1)[1:] or [""]
        found.append(urlunsplit((parts.scheme, parts.netloc, f"/en/{rest[0]}", "", "")))
    return found


def candidates(url: str, html: str, links: list[Candidate], country: str,
               languages: list[str], guess: bool) -> list[tuple[str, bool]]:
    """(URL, it must itself be the country's version) in the owner's order; URLs are
    guessed and a Finland / Nordic page (any URL) is taken only when `guess` (a foreign
    version: a global page keeps its own way to the country, e.g. Beckhoff)."""
    named = declared(html, url, country) + switchers(links, country)
    found = [(u, True) for u in named + (constructed(url, country, languages) if guess else [])]
    found += [(u, False) for u in region_pages(links)] if guess else []
    return list(dict.fromkeys(found))
