"""job.finished: store the run result, release the lease, set state/continuation.

Requires `last_content_seq == seq - 1` with every earlier seq recorded (else
sequence_gap, not recorded). Only the current run of a non-cancelled job,
delivered under its full lease, changes job state; a late finished (drain-only,
old run, cancelled job, or a run that already finished) is still accepted with
state_applied=false and never finishes a newer run.
"""

from __future__ import annotations

from contract_server.event_context import Batch, Outcome, rejected
from contract_server.leases import DRAIN, FULL, release_lease
from contract_server.util import Json

RESULT_FIELDS = (
    "run_result_status",
    "completion_reason",
    "coverage",
    "gaps",
    "checkpoint",
    "budget",
    "counts",
    "continuation_requested",
    "active_seconds",
)
DEFAULT_MAX_RUNS = 6
DEFAULT_CAMPAIGN_SECONDS = 10800


def budget_remains(policy: Json, budget: Json, runs_used: int) -> bool:
    """Every campaign limit (incl. max_runs) still has room; cloud 0 means 'no cloud'."""
    limits = (
        (budget["campaign_pages"], policy["campaign_max_pages"]),
        (budget["campaign_states"], policy["campaign_max_states"]),
        (budget["campaign_browser_actions"], policy["campaign_max_browser_actions"]),
        (
            budget["campaign_active_seconds"],
            policy.get("max_campaign_active_seconds", DEFAULT_CAMPAIGN_SECONDS),
        ),
        (runs_used, policy.get("max_runs", DEFAULT_MAX_RUNS)),
    )
    if any(used >= limit for used, limit in limits):
        return False
    cloud = policy["campaign_cloud_budget_eur"]
    return not (cloud > 0 and budget["campaign_cloud_eur"] >= cloud)


def apply_to_job(job: Json, payload: Json) -> bool:
    """New job state and continuation; True when the next run is scheduled."""
    job["state"] = payload["run_result_status"]
    policy = job["policy"]
    room = budget_remains(policy, payload["budget"], len(job["run_ids"]))
    if policy.get("auto_continue", True) and payload["continuation_requested"] and room:
        job["state"] = "queued"
        job["continuation"] = "scheduled"
        return True
    job["continuation"] = "none" if room else "budget_exhausted"
    return False


def store_result(batch: Batch, payload: Json, now: float) -> None:
    run = batch.run
    run["result"] = {name: payload[name] for name in RESULT_FIELDS}
    run["finished"] = True
    run["finished_at"] = now
    release_lease(run, now, token_was_lease=batch.rights == FULL)
    batch.job["counts_snapshot"] = payload["counts"]


def apply(batch: Batch, event: Json) -> Outcome:
    payload, seq = event["payload"], event["seq"]
    if payload["last_content_seq"] != seq - 1 or batch.run["last_contiguous_seq"] != seq - 1:
        detail = f"job.finished needs last_content_seq = {seq - 1}"
        return rejected("sequence_gap", detail, record=False)
    if batch.run["finished"]:
        return Outcome(state_applied=False)  # a late repeat: accepted, first result kept
    store_result(batch, payload, batch.stand.now())
    applied = batch.applies and batch.job["state"] != "cancelled"
    if applied:
        batch.next_run_scheduled = apply_to_job(batch.job, payload)
    batch.rights = DRAIN
    return Outcome(state_applied=applied)
