"""Choosing the next action: structure rules, link rules, else the best-ranked link.

S6 step 6.1 (TZ_SELAIN v4.0 4.1, owner 10.10.2026): no model chooses a step any
more. Until 0.4.8.12 a navigation model (7b) picked the next link, a vision model
looked at a page without DOM text, and a menu cache repeated an earlier choice. On
MAIN-PC the two small models were never even pulled - every call failed and the card
model took over - and on all eight stands the rules alone found the same 109 people
(`docs/ARGUS20_COLLECTOR_SELFAUDIT.md` 3). So the walk is deterministic: a structure
rule, then a link rule, then the best-ranked link. The model only reads what the
rules could not (`cards.py`). A page read before is never the target, through a
redirect neither; an unvisited link is no reason not to finish. The page budget
holds for every answer.
"""

from __future__ import annotations

from dataclasses import replace

from argus_collector.browser import contract as browser
from argus_collector.discovery import contract as discovery
from argus_collector.walk import page as page_step
from argus_collector.walk import prompts, rules, service, structure
from argus_collector.walk.service import Action
from argus_collector.walk.state import MAX_STALLED, WalkState


def end_budget(state: WalkState) -> None:
    """Budget used: every relevant link left is a resumable gap `budget_reached`."""
    state.end_reason = service.END_BUDGET
    state.gap_unwalked("budget_reached", "the run budget was used up before this link")


def end_stalled(state: WalkState, url: str) -> None:
    """MAX_STALLED actions without a new page state (a redirect loop, Kontaktit 05.10.2026):
    the walk ends; the links left are gaps `no_progress`, not resumable - the same site would
    loop again in the next run."""
    state.end_reason = service.END_NO_PROGRESS
    detail = f"{MAX_STALLED} actions in a row without a new page state"
    state.add_gap(url, "no_progress", detail, False)
    state.gap_unwalked("no_progress", detail, resumable=False)


def _unread(state: WalkState, action: Action) -> Action:
    """A navigation to a page read before (or to a link that led to one) finishes."""
    cand = action.candidate
    if action.kind != service.ACTION_NAVIGATE or cand is None:
        return action
    if discovery.normalize_url(cand.href) in state.walked():
        state.step(service.STEP_LOOP, f"{cand.href}: read before", cand.href)
        return Action(service.ACTION_FINISH, source="read_before")
    return action


def decide(state: WalkState, wb: browser.WalkBrowser, page: browser.PageState,
           text: str) -> Action:
    finished = discovery.normalize_url(page.url) in state.finished_urls  # finish_branch
    built = None if finished else structure.structural_action(state, page)
    if built is not None:
        return replace(built, source="structure")
    candidates = page_step.ranked(state, page)
    if not candidates:
        return Action(service.ACTION_FINISH, source="finish_branch" if finished else "finish")
    action = rules.rule_action(state, page, candidates)
    if action is None:  # no rule link: the best-ranked candidate, still the rules' choice
        action = replace(prompts.fallback_action(candidates), source="rules")
    action = _unread(state, action)
    pages_left = state.settings.run_limits().pages - state.cp.pages
    if action.kind == service.ACTION_NAVIGATE and pages_left <= 0:
        end_budget(state)
        return Action(service.ACTION_FINISH, source="budget")
    return action
