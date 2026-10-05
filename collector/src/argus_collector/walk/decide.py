"""Choosing the next action: model answer, fallback, finish guard, page budget."""

from __future__ import annotations

from argus_collector.browser import contract as browser
from argus_collector.discovery import contract as discovery
from argus_collector.models import contract as models
from argus_collector.walk import page as page_step
from argus_collector.walk import prompts, service, structure
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
            return Action(service.ACTION_NAVIGATE, cand)
    return Action(service.ACTION_FINISH)


def decide(state: WalkState, page: browser.PageState, text: str) -> Action:
    built = structure.structural_action(state, page)
    if built is not None:
        return built
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
