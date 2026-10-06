"""Next steps that need no model (owner 05.10.2026: rules, then 7b, 14b, VL).

Taken in this order from the walk's ranked, unvisited links on approved hosts:
1. the exhibition-country version (`Finland`, `Suomi`, `/fi-fi/`) while the
   current page is not that version;
2. the country finder (`Global presence`, `Beckhoff Worldwide`) while the
   current page is not that version and names the exhibition country nowhere;
3. a contact or people page by its own words (`Yhteystiedot`, `Contact`,
   `Kontakt`, `Henkilöstö`; the country bonus of every `/fi/` link not counted).
When none applies, the decision cache or the navigation model chooses.
The menu cache: the model's choice for a set of links is reused while the
same links are shown and the chosen one is still unvisited.
"""

from __future__ import annotations

import hashlib

from argus_collector.browser import contract as browser
from argus_collector.discovery import contract as discovery
from argus_collector.walk import service
from argus_collector.walk.service import Action
from argus_collector.walk.state import WalkState

LINK = "link"


def _open_links(state: WalkState, candidates: list[discovery.Candidate]) -> list[
        discovery.Candidate]:
    visited = state.walked()
    return [
        c for c in candidates
        if c.kind == LINK and discovery.is_allowed_url(c.href, state.hosts)
        and discovery.normalize_url(c.href) not in visited
        and discovery.normalize_url(c.href) not in state.failed_targets
    ]


def _country_version(country: str, cand: discovery.Candidate) -> bool:
    return (discovery.label_country(cand.text) == country
            or discovery.url_country(cand.href) == country)


def rule_action(
    state: WalkState, page: browser.PageState, candidates: list[discovery.Candidate]
) -> Action | None:
    """The next step by a rule, None when the model has to choose."""
    links = _open_links(state, candidates)
    country = state.focus.country if state.focus is not None else ""
    away = bool(country) and discovery.url_country(page.url) != country
    if away:
        for cand in links:
            if _country_version(country, cand):
                return Action(service.ACTION_NAVIGATE, cand, source="rule")
        named = any(discovery.label_country(c.text) == country for c in page.candidates)
        for cand in links if not named else []:
            if discovery.is_worldwide(cand.text):
                return Action(service.ACTION_NAVIGATE, cand, source="rule")
    for cand in links:
        if discovery.contact_link(cand.text, cand.href):
            return Action(service.ACTION_NAVIGATE, cand, source="rule")
    return None


def menu_key(state: WalkState, candidates: list[discovery.Candidate]) -> str:
    """The same links in any order on any page give the same key."""
    country = state.focus.country if state.focus is not None else ""
    items = sorted(f"{c.kind}|{c.text}|{discovery.normalize_url(c.href) if c.href else ''}"
                   for c in candidates)
    return hashlib.sha256("\n".join([country, *items]).encode("utf-8")).hexdigest()[:16]


def cached_action(
    state: WalkState, key: str, candidates: list[discovery.Candidate]
) -> Action | None:
    """The model's earlier choice for this menu while that link is still unvisited
    (only links: a cached click could repeat itself)."""
    chosen = state.menu_cache.get(key)
    if chosen is None:
        return None
    for cand in _open_links(state, candidates):
        if (cand.text, cand.href) == chosen:
            return Action(service.ACTION_NAVIGATE, cand, source="cache")
    return None


def remember(state: WalkState, key: str, action: Action) -> None:
    if action.candidate is not None and action.kind == service.ACTION_NAVIGATE:
        state.menu_cache[key] = (action.candidate.text, action.candidate.href)
