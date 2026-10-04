"""Single entry point of the `discovery` module (pure).

Which URLs a walk may open and in what order: approved hosts (K7: exact host
match, no suffix comparison), no social networks (K8), no mailto/tel/
javascript, no documents (M2), contact-word ranking of links, page keys.
"""

from __future__ import annotations

from argus_collector.discovery import focus as focus_rules
from argus_collector.discovery import service
from argus_collector.discovery.focus import Focus
from argus_collector.discovery.service import Candidate

__all__ = [
    "Candidate",
    "Focus",
    "approved_hosts_for",
    "focus_brief",
    "host_of",
    "link_language",
    "make_focus",
    "is_allowed_url",
    "is_social_url",
    "normalize_url",
    "page_key",
    "rank_candidates",
    "score_link",
]


def normalize_url(url: str) -> str:
    """Scheme+host lower-cased, fragment dropped, default port dropped, no trailing `/` on paths."""
    return service.normalize_url(url)


def approved_hosts_for(start_url: str, final_url: str) -> frozenset[str]:
    """Hosts a walk may touch: the seed host and the host it redirected to."""
    return service.approved_hosts_for(start_url, final_url)


def is_social_url(url: str) -> bool:
    return service.is_social_url(url)


def is_allowed_url(url: str, hosts: frozenset[str]) -> bool:
    """http(s), host in `hosts` exactly, not social, not a document download."""
    return service.is_allowed_url(url, hosts)


def score_link(text: str, href: str, focus: Focus | None = None) -> int:
    """Higher for contact/team/staff/yhteystiedot/henkilosto words in text or path;
    with a focus also for the exhibition country, its language and export people."""
    return service.score_link(text, href, focus)


def rank_candidates(
    candidates: list[Candidate],
    visited: set[str],
    hosts: frozenset[str],
    focus: Focus | None = None,
) -> list[Candidate]:
    """Candidates the model may pick: allowed links not yet visited (by normalised
    URL, de-duplicated) plus all buttons; links sorted by score, buttons after."""
    return service.rank_candidates(candidates, visited, hosts, focus)


def make_focus(countries: list[str], languages: list[str]) -> Focus | None:
    """Focus from scope.priority_countries / priority_languages; None when both are empty."""
    return focus_rules.make_focus(countries, languages)


def link_language(text: str, href: str) -> str | None:
    """Language a language-switch link leads to (`Suomi` -> `fi`, `/de-de/` -> `de`)."""
    return focus_rules.link_language(text, href)


def focus_brief(focus: Focus | None) -> str:
    """The focus as English instructions for the model's action prompt."""
    return focus_rules.focus_brief(focus)


def host_of(url: str) -> str:
    """Host compared with approved_hosts: lower case, `www.` stripped, no port."""
    return service.host_of(url)


def page_key(url: str, text_sha256: str) -> str:
    """State key of a page: normalised URL + content hash (TZ section 8.5)."""
    return service.page_key(url, text_sha256)
