"""Pure rules of discovery: URL normalisation, host policy, link ranking."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

from argus_collector.discovery import repository as tables
from argus_collector.discovery.focus import Focus, focus_score

KIND_LINK = "link"
KIND_BUTTON = "button"
WORD_RE = re.compile(r"[a-zåäöøæ»>]+", re.IGNORECASE)
DEFAULT_PORTS = {"http": "80", "https": "443"}


@dataclass(frozen=True)
class Candidate:
    """One element the model may act on, numbered as shown to it.

    `kind` is `link` (has an http(s) href; acted on by navigation) or
    `button` (button, role=button, summary, link without href; acted on by
    click). `selector` finds the element again on the current page.
    """

    index: int
    kind: str
    text: str
    href: str
    selector: str


def _host(url: str) -> str:
    try:
        parts = urlsplit(url)
    except ValueError:
        return ""
    host = (parts.hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def host_of(url: str) -> str:
    return _host(url)


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


def score_link(text: str, href: str, focus: Focus | None = None) -> int:
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
    return score + focus_score(text, href, focus)


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
        if cand.kind == KIND_BUTTON:
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
