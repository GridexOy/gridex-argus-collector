"""Choosing the next action: structure and link rules, the menu cache, a model.

Routing (owner 05.10.2026): a structure rule or a link rule needs no model;
then the menu cache; a page without DOM text goes to the vision model with
its screenshot; else the navigation model (7b) chooses, the card model when
the navigation model fails. The finish guard and the page budget hold for
every answer.
"""

from __future__ import annotations

from dataclasses import replace

from argus_collector.browser import contract as browser
from argus_collector.discovery import contract as discovery
from argus_collector.models import contract as models
from argus_collector.walk import page as page_step
from argus_collector.walk import prompts, rules, service, structure, vision
from argus_collector.walk.service import Action
from argus_collector.walk.state import WalkState


def end_budget(state: WalkState) -> None:
    """Budget used: every relevant link left is a resumable gap `budget_reached`."""
    state.end_reason = service.END_BUDGET
    state.gap_unwalked("budget_reached", "the run budget was used up before this link")


def _guard_finish(state: WalkState, candidates: list[discovery.Candidate]) -> Action:
    """In job mode the model may not finish while a strong contact link is unvisited."""
    for cand in candidates:
        if cand.kind == "link" and discovery.strong_link(cand.text, cand.href, state.focus):
            return Action(service.ACTION_NAVIGATE, cand, source="guard")
    return Action(service.ACTION_FINISH, source="finish")


def _ask(state: WalkState, system: str, user: str,
         candidates: list[discovery.Candidate]) -> Action:
    """The navigation model; once it fails (not pulled, down) the card model takes over."""
    client = state.navigator()
    try:
        reply = client.chat_json(system, user, prompts.PURPOSE_ACTION)
    except models.ModelError:
        if client is state.client:
            raise
        state.navigation_failed()
        client = state.client
        reply = client.chat_json(system, user, prompts.PURPOSE_ACTION)
    return replace(prompts.parse_action(reply, candidates), source=f"model:{client.config.name}")


def _model_action(
    state: WalkState, wb: browser.WalkBrowser, page: browser.PageState, text: str,
    candidates: list[discovery.Candidate],
) -> Action:
    pages_left = state.settings.run_limits().pages - state.cp.pages
    state.step(service.STEP_MODEL, "action", page.url)
    brief = discovery.focus_brief(state.focus)
    system, user = prompts.action_prompt(page.url, page.title, text, candidates, pages_left,
                                         brief)
    try:
        seen = vision.action_without_text(state, wb, page, text, (system, user), candidates)
        return seen if seen is not None else _ask(state, system, user, candidates)
    except models.ModelError as exc:
        state.step(service.STEP_MODEL, f"action failed: {exc}", page.url)
        return replace(prompts.fallback_action(candidates), source="fallback")


def decide(state: WalkState, wb: browser.WalkBrowser, page: browser.PageState,
           text: str) -> Action:
    built = structure.structural_action(state, page)
    if built is not None:
        return replace(built, source="structure")
    candidates = page_step.ranked(state, page)
    if not candidates:
        return Action(service.ACTION_FINISH, source="finish")
    key = rules.menu_key(state, page.candidates)
    action = rules.rule_action(state, page, candidates) or rules.cached_action(
        state, key, candidates)
    if action is None:
        action = _model_action(state, wb, page, text, candidates)
        rules.remember(state, key, action)
    if action.kind == service.ACTION_FINISH and state.job_mode:
        action = _guard_finish(state, candidates)
    pages_left = state.settings.run_limits().pages - state.cp.pages
    if action.kind == service.ACTION_NAVIGATE and pages_left <= 0:
        end_budget(state)
        return Action(service.ACTION_FINISH, source="budget")
    return action
