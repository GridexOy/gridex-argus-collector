"""Structure rules applied before the model chooses (TZ_SELAIN 8.4 guard-rails).

Owner decisions 05.10.2026:
1. A country list (accordion headers, tabs, a dropdown, links naming >= 3
   countries): only the exhibition country is opened or selected; the other
   countries' controls are not offered to the model and not remembered.
2. Department tabs, and collapsed department sections on a page with
   contacts: every one is opened once, sales and marketing first.
Each structural action is done once per page URL and label (`cp.acted`).
"""

from __future__ import annotations

from argus_collector.browser import contract as browser
from argus_collector.discovery import contract as discovery
from argus_collector.walk import service
from argus_collector.walk.service import Action
from argus_collector.walk.state import WalkState

MAX_EXPANDS = 12  # collapsed sections opened per page
TAB, EXPAND, ON = "tab", "expand", "on"


def _key(url: str, cand: discovery.Candidate, label: str) -> str:
    return f"{discovery.normalize_url(url)}|{cand.role or cand.kind}|{label}"


def _country(state: WalkState) -> str:
    return state.focus.country if state.focus is not None else ""


def offered(state: WalkState, candidates: list[discovery.Candidate]) -> list[discovery.Candidate]:
    """Candidates without the other countries of a country list (and without dropdowns)."""
    members = discovery.country_members(candidates)
    country = _country(state)
    others = {
        id(c) for code, group in members.items() if code != country for c in group
        if c.kind != discovery.KIND_SELECT
    }
    return [c for c in candidates if id(c) not in others and c.kind != discovery.KIND_SELECT]


def _once(state: WalkState, url: str, cand: discovery.Candidate, label: str) -> bool:
    """True the first time; records the action so it is never repeated."""
    key = _key(url, cand, label)
    if key in state.cp.acted:
        return False
    state.cp.acted.append(key)
    return True


def _open_country(state: WalkState, page: browser.PageState) -> Action | None:
    country = _country(state)
    members = discovery.country_members(page.candidates) if country else {}
    for cand in members.get(country, []):
        if cand.kind == discovery.KIND_SELECT:
            option = next(o for o in cand.options if discovery.label_country(o) == country)
            if discovery.label_country(cand.state) != country and _once(state, page.url, cand,
                                                                        option):
                return Action(service.ACTION_SELECT, cand, option)
        elif cand.kind == discovery.KIND_BUTTON:
            if cand.state != ON and _once(state, page.url, cand, cand.text):
                return Action(service.ACTION_CLICK, cand)
        elif discovery.is_allowed_url(cand.href, state.hosts):
            if discovery.normalize_url(cand.href) not in state.cp.visited:
                return Action(service.ACTION_NAVIGATE, cand)
    return None


def _departments(state: WalkState, page: browser.PageState) -> Action | None:
    tabs = [c for c in page.candidates if c.role == TAB and not discovery.label_country(c.text)]
    sections = [c for c in page.candidates if c.role == EXPAND and c.state != ON
                and not discovery.label_country(c.text)][:MAX_EXPANDS]
    pool = tabs if len(tabs) >= 2 else []
    if state.page_has_contacts:
        pool += sections
    for cand in pool:
        if cand.state == ON:
            _once(state, page.url, cand, cand.text)
    order = sorted(pool, key=lambda c: (discovery.department_rank(c.text), c.index))
    for cand in order:
        if cand.state != ON and _once(state, page.url, cand, cand.text):
            return Action(service.ACTION_CLICK, cand)
    return None


def structural_action(state: WalkState, page: browser.PageState) -> Action | None:
    """The next structure action of this page state, None when the model decides."""
    return _open_country(state, page) or _departments(state, page)
