"""Pure rules of discovery: URL normalisation, host policy, link ranking."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

from argus_collector.discovery import countries
from argus_collector.discovery import repository as tables
from argus_collector.discovery.focus import Focus, focus_score, link_language

KIND_LINK = "link"
KIND_BUTTON = "button"
KIND_SELECT = "select"
STRONG_LINK_SCORE = 10  # a link the model may not skip before finishing (guard-rail)
COUNTRY_LIST_MIN = 3  # distinct countries that make a page a country list
WORD_RE = re.compile(r"[a-zåäöøæ»>]+", re.IGNORECASE)
DEFAULT_PORTS = {"http": "80", "https": "443"}


@dataclass(frozen=True)
class Candidate:
    """One element the model may act on, numbered as shown to it.

    `kind` is `link` (has an http(s) href; acted on by navigation),
    `button` (button, role=button/tab, summary, accordion header, link
    without href; acted on by click) or `select` (a dropdown; `options` are
    its option labels). `role` is `tab` / `expand` / "" and `state` is `on`
    for a selected tab or an expanded header. `selector` finds the element
    again on the current page.
    """

    index: int
    kind: str
    text: str
    href: str
    selector: str
    role: str = ""
    state: str = ""
    options: tuple[str, ...] = ()


def _host(url: str) -> str:
    try:
        parts = urlsplit(url)
    except ValueError:
        return ""
    host = (parts.hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def host_of(url: str) -> str:
    return _host(url)


SECOND_LEVEL = frozenset({"co.uk", "org.uk", "ac.uk", "com.au", "co.nz", "co.jp", "com.br",
                          "com.cn", "com.mx", "com.ar", "com.tr", "co.za", "co.in", "com.sg"})


def site_domain(host: str) -> str:
    """The registrable domain of a host (`industryx.dimecc.com` -> `dimecc.com`); an IP stays."""
    labels = host.lower().rstrip(".").split(".")
    if all(part.isdigit() for part in labels):
        return host
    keep = 3 if ".".join(labels[-2:]) in SECOND_LEVEL else 2
    return ".".join(labels[-keep:])


def normalize_url(url: str) -> str:
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return url.strip()
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower()
    port = f":{parts.port}" if parts.port and str(parts.port) != DEFAULT_PORTS.get(scheme) else ""
    path = parts.path or "/"
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    return urlunsplit((scheme, host + port, path, parts.query, ""))


def approved_hosts_for(start_url: str, final_url: str) -> frozenset[str]:
    return frozenset(h for h in (_host(start_url), _host(final_url)) if h)


def is_social_url(url: str) -> bool:
    host = _host(url)
    return any(host == s or host.endswith("." + s) for s in tables.SOCIAL_HOSTS)


def is_allowed_url(url: str, hosts: frozenset[str]) -> bool:
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    if parts.scheme.lower() not in ("http", "https"):
        return False
    if _host(url) not in hosts or is_social_url(url):
        return False
    return not parts.path.lower().endswith(tables.DOCUMENT_SUFFIXES)


def base_score(text: str, href: str) -> int:
    """Contact / noise words of a link without the exhibition-country focus."""
    words = {w.lower() for w in WORD_RE.findall(text)}
    path_words = {w.lower() for w in WORD_RE.findall(urlsplit(href).path.replace("-", " "))}
    score = 0
    for word, weight in tables.CONTACT_WORDS.items():
        if word in words:
            score += weight
        if word in path_words:
            score += weight // 2
    for word, weight in tables.NOISE_WORDS.items():
        if word in words or word in path_words:
            score += weight
    if any(w in text.lower() for w in tables.NEXT_WORDS):
        score += 5
    return score


def score_link(text: str, href: str, focus: Focus | None = None) -> int:
    score = base_score(text, href) + focus_score(text, href, focus)
    if focus is not None and focus.country and countries.url_country(href) == focus.country:
        score += tables.FOCUS_COUNTRY_BONUS  # `/fi-fi/`, `fi.` host, `.fi` version
    return score


def is_version_switch(text: str, href: str) -> bool:
    """A link to another language / country version: `Svenska`, `SE`, `/sv-se/`."""
    if link_language(text, "") or countries.label_country(text):
        return True
    path = urlsplit(href).path.strip("/")
    return bool(path) and "/" not in path and countries.url_country(href) is not None


def strong_link(text: str, href: str, focus: Focus | None) -> bool:
    """The model may not finish while such a link is unvisited (job mode guard).

    A contact link, a link to the exhibition-country version, and, when the
    seed already is that version, the switch to another country version (it
    is walked after, owner 05.10.2026)."""
    if max(base_score(text, href), score_link(text, href, focus)) >= STRONG_LINK_SCORE:
        return True
    if focus is None or not focus.local_seed:
        return False
    other = countries.link_country(text, href)
    return other is not None and other != focus.country and is_version_switch(text, href)


def country_members(candidates: list[Candidate]) -> dict[str, list[Candidate]]:
    """Controls and links labelled with a country; a country list when >= 3 countries."""
    found: dict[str, list[Candidate]] = {}
    for cand in candidates:
        labels = cand.options if cand.kind == KIND_SELECT else (cand.text,)
        for label in labels:
            code = countries.label_country(label)
            if code is not None:
                found.setdefault(code, []).append(cand)
    return found if len(found) >= COUNTRY_LIST_MIN else {}


def rank_candidates(
    candidates: list[Candidate],
    visited: set[str],
    hosts: frozenset[str],
    focus: Focus | None = None,
) -> list[Candidate]:
    seen = set(visited)
    links: list[tuple[int, int, Candidate]] = []
    buttons: list[Candidate] = []
    for cand in candidates:
        if cand.kind != KIND_LINK:
            buttons.append(cand)
            continue
        key = normalize_url(cand.href)
        if key in seen or not is_allowed_url(cand.href, hosts):
            continue
        seen.add(key)
        links.append((-score_link(cand.text, cand.href, focus), cand.index, cand))
    links.sort()
    return [c for _, _, c in links] + buttons


def page_key(url: str, text_sha256: str) -> str:
    return f"{normalize_url(url)}#{text_sha256[:16]}"
