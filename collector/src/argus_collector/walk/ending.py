"""How a walk ends by its goal (owner 06.10.2026): the panel line and the done event.

Once the goal is reached, the contact / team / henkilöstö / yhteystiedot links
the walk has already found are still read, at most 2 (owner 06.10.2026, 0.4.8.7);
then the walk ends. 2 more pages without the goal end it too.
"""

from __future__ import annotations

from dataclasses import replace
from urllib.parse import urlsplit

from argus_collector.browser import contract as browser
from argus_collector.discovery import contract as discovery
from argus_collector.walk import goal, service
from argus_collector.walk import page as page_step
from argus_collector.walk.service import Action, WalkEvent
from argus_collector.walk.state import WalkState

FOLLOWUPS = 2  # found contact links read after the goal
FOLLOW_WORDS = ("team", "tiimi", "henkilosto", "henkilokunta", "yhteystiedot", "yhteyshenkilot",
                "contact", "kontakt", "people", "staff", "personnel", "ansprechpartner",
                "medarbetare", "personal")


def _people_link(cand: discovery.Candidate) -> bool:
    """team / henkilöstö / yhteystiedot and the like by the link's text or path."""
    words = goal.fold(f"{cand.text} {urlsplit(cand.href).path}")
    return cand.kind == "link" and any(word in words for word in FOLLOW_WORDS)


def _followup(state: WalkState, page: browser.PageState) -> Action | None:
    if state.goal.followups >= FOLLOWUPS:
        return None
    links = [c for c in page_step.ranked(state, page) if _people_link(c)]
    if not links:
        return None
    state.goal.followups += 1
    return Action(service.ACTION_NAVIGATE, links[0], source="goal_followup")


def after_goal(state: WalkState, page: browser.PageState) -> Action | None:
    """Asked before every next action: None goes on as decided; else a found contact link
    after the goal, or finish (`Tavoite saavutettu`)."""
    end = goal.verdict(state.goal, state.cp.pages) if state.settings.stop_at_goal else None
    if end is None:
        return None
    follow = _followup(state, page) if end == service.END_GOAL else None
    if follow is not None:
        return follow
    state.end_reason = end
    step = service.STEP_GOAL if end == service.END_GOAL else service.STEP_GOAL_PAGES
    state.emit(WalkEvent(service.EVENT_STEP, url=page.url, step=step,
                         people=len(state.goal.people), channels=state.goal.channels))
    return Action(service.ACTION_FINISH, source="goal")


def done_event(state: WalkState, result: str) -> WalkEvent:
    """EVENT_DONE; after a goal end it carries the goal step, people and channels."""
    done = WalkEvent(service.EVENT_DONE, detail=result, page_no=state.cp.pages)
    if state.end_reason not in (service.END_GOAL, service.END_GOAL_PAGES):
        return done
    step = service.STEP_GOAL if state.end_reason == service.END_GOAL else service.STEP_GOAL_PAGES
    return replace(done, step=step, people=len(state.goal.people),
                   channels=state.goal.channels)
