"""Pure rules of the scheduler: local job states, run budget, run outcome."""

from __future__ import annotations

from dataclasses import dataclass

from argus_collector.discovery import contract as discovery
from argus_collector.walk.contract import (
    END_BUDGET,
    END_DOMAIN,
    END_FAILURES,
    END_FINISHED,
    END_GOAL,
    END_GOAL_PAGES,
    END_NO_PROGRESS,
    END_START_FAILED,
    WalkLimits,
)

MAX_JOBS = 8  # companies per worker (TZ_SELAIN 8.13)

# Local job states (`jobs.state`).
QUEUED = "queued"  # claimed, waiting for the browser
RUNNING = "running"  # the browser walks it now
STOPPED = "stopped"  # Pysayta / STOP / panel closed mid-walk: resumes on Kaynnista
PAUSED = "paused"  # paused from ARGUS (command pause)
WAITING_LEASE = "waiting_lease"  # lease expired or mismatched: reconcile first
NEEDS_ATTENTION = "needs_attention"  # a bot check did not clear: the owner solves it
COMPLETED, PARTIAL, FAILED, CANCELLED = "completed", "partial", "failed", "cancelled"
ACTIVE = (QUEUED, RUNNING, STOPPED, PAUSED, WAITING_LEASE, NEEDS_ATTENTION)
RUNNABLE = (QUEUED, STOPPED)
TERMINAL = (COMPLETED, PARTIAL, FAILED, CANCELLED)

# Stages (`jobs.stage`, the Vaihe column).
STAGE_QUEUED = "queued"
STAGE_BROWSER = "browser"
STAGE_FINALIZING = "finalizing"

# Why a walk was interrupted from outside (the job is not finished then).
STOP_COLLECTING = "stop"  # Pysayta, STOP file
STOP_PAUSE = "pause"  # command pause
STOP_CANCEL = "cancel"  # command cancel / lease cancelled
STOP_LEASE = "lease"  # lease expired or lost

PURPOSES = {"walk.cards": "card_parsing", "walk.action": "action_planning",
            "walk.vision": "vision"}


@dataclass(frozen=True)
class Consumed:
    """What earlier runs of the campaign used (ClaimedJob.checkpoint)."""

    seconds: float = 0.0
    pages: int = 0
    actions: int = 0


def run_limits(policy: dict[str, float], used: Consumed) -> WalkLimits:
    """Run budget = the policy's run limits capped by what is left of the campaign."""
    pages = min(int(policy["max_pages"]), int(policy["campaign_max_pages"]) - used.pages)
    actions = min(
        int(policy["max_browser_actions"]),
        int(policy["campaign_max_browser_actions"]) - used.actions,
    )
    seconds = min(
        float(policy["max_active_seconds"]),
        float(policy.get("max_campaign_active_seconds", 10800)) - used.seconds,
    )
    states = int(policy["max_states"])
    return WalkLimits(max(0, pages), max(0, actions), max(0.0, seconds), max(0, states))


def outcome(end_reason: str, found: bool, cancelled: bool) -> tuple[str, str]:
    """(run_result_status, completion_reason) of a walk that ended (TZ_SELAIN 8.10)."""
    if cancelled:
        return CANCELLED, "manual_cancel"
    if end_reason in (END_FINISHED, END_NO_PROGRESS):  # no_progress: the gap says why
        return COMPLETED, "frontier_exhausted" if found else "no_contacts_in_checked_scope"
    if end_reason in (END_GOAL, END_GOAL_PAGES):  # contract 1.1 has no `goal_reached`
        return COMPLETED, "frontier_exhausted"
    if end_reason == END_BUDGET:
        return PARTIAL, "budget_reached"
    if end_reason == END_DOMAIN:
        return PARTIAL, "unresolved_access"
    if end_reason == END_FAILURES:
        return PARTIAL, "technical_failure"
    if end_reason == END_START_FAILED:
        return FAILED, "technical_failure"
    return FAILED, "technical_failure"


def frontier_status(end_reason: str, pages: int) -> str:
    if pages == 0:
        return "not_started"
    return "exhausted" if end_reason == END_FINISHED else "partial"


OWN_BASES = ("seed", "redirect_from_seed", "owner_known_url", "business_id_match")


def company_domains(approvals: list[tuple[str, str]], seed_host: str) -> frozenset[str]:
    """Registrable domains people and channels may come from (K7, owner 06.10.2026): the
    seed's and those of hosts approved as the company's own; a host approved only as
    `linked_from_contact_section` (an event page, a directory) gives no people."""
    own = {discovery.site_domain(host) for host, basis in approvals if basis in OWN_BASES}
    return frozenset(own | {discovery.site_domain(seed_host)})


def purpose(local: str) -> str:
    """Walk purpose -> ModelUsage.purpose (`walk.cards:retry` is still card parsing)."""
    return PURPOSES.get(local.split(":", 1)[0], "action_planning")


def free_slots(active_jobs: int, max_jobs: int = MAX_JOBS) -> int:
    return max(0, max_jobs - active_jobs)
