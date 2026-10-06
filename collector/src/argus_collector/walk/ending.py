"""How a walk ends by its goal (owner 06.10.2026): the panel line and the done event."""

from __future__ import annotations

from dataclasses import replace

from argus_collector.walk import goal, service
from argus_collector.walk.service import WalkEvent
from argus_collector.walk.state import WalkState


def reached(state: WalkState, url: str) -> bool:
    """Asked before every next action: True ends the walk (`Tavoite saavutettu`)."""
    end = goal.verdict(state.goal, state.cp.pages) if state.settings.stop_at_goal else None
    if end is None:
        return False
    state.end_reason = end
    step = service.STEP_GOAL if end == service.END_GOAL else service.STEP_GOAL_PAGES
    state.emit(WalkEvent(service.EVENT_STEP, url=url, step=step,
                         people=len(state.goal.people), channels=state.goal.channels))
    return True


def done_event(state: WalkState, result: str) -> WalkEvent:
    """EVENT_DONE; after a goal end it carries the goal step, people and channels."""
    done = WalkEvent(service.EVENT_DONE, detail=result, page_no=state.cp.pages)
    if state.end_reason not in (service.END_GOAL, service.END_GOAL_PAGES):
        return done
    step = service.STEP_GOAL if state.end_reason == service.END_GOAL else service.STEP_GOAL_PAGES
    return replace(done, step=step, people=len(state.goal.people),
                   channels=state.goal.channels)
