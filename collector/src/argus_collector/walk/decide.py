"""Choosing the next action: model answer, fallback, finish guard, page budget."""

from __future__ import annotations

from argus_collector.browser import contract as browser
from argus_collector.discovery import contract as discovery
from argus_collector.models import contract as models
from argus_collector.walk import page as page_step
from argus_collector.walk import prompts, service
from argus_collector.walk.service import Action
from argus_collector.walk.state import WalkState

STRONG_LINK_SCORE = 10  # a contact/team/country link the model may not skip (guard-rail)


def end_budget(state: WalkState) -> None:
    state.end_reason = service.END_BUDGET
    if state.cp.frontier:
        best = max(state.cp.frontier.values(), key=lambda link: link.score)
        detail = f"run budget used; {len(state.cp.frontier)} links left in the frontier"
        state.add_gap(best.url, "budget_reached", detail, True)


def _guard_finish(state: WalkState, candidates: list[discovery.Candidate]) -> Action:
    """In job mode the model may not finish while a strong contact link is unvisited."""
    for cand in candidates:
        if cand.kind == "link":
            if discovery.score_link(cand.text, cand.href, state.focus) >= STRONG_LINK_SCORE:
                return Action(service.ACTION_NAVIGATE, cand)
    return Action(service.ACTION_FINISH)


def decide(state: WalkState, page: browser.PageState, text: str) -> Action:
    candidates = page_step.ranked(state, page)
    pages_left = state.settings.run_limits().pages - state.cp.pages
    if not candidates:
        return Action(service.ACTION_FINISH)
    state.step(service.STEP_MODEL, "action", page.url)
    brief = discovery.focus_brief(state.focus)
    system, user = prompts.action_prompt(
        page.url, page.title, text, candidates, pages_left, brief
    )
    try:
        action = prompts.parse_action(
            state.client.chat_json(system, user, prompts.PURPOSE_ACTION), candidates
        )
    except models.ModelError as exc:
        state.step(service.STEP_MODEL, f"action failed: {exc}", page.url)
        action = prompts.fallback_action(candidates)
    if action.kind == service.ACTION_FINISH and state.job_mode:
        action = _guard_finish(state, candidates)
    if action.kind == service.ACTION_NAVIGATE and pages_left <= 0:
        end_budget(state)
        return Action(service.ACTION_FINISH)
    return action
