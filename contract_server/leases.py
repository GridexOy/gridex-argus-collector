"""Leases, drain tokens and the execution-token check for evidence and events.

A run carries one lease (`lease_token`, `generation`, `lease_expires`) and
optionally one drain token (`drain_token`, `drain_expires`). A drain token
lets a worker deliver the uploads/events of that run without changing any
state. When a run finishes under its lease, the lease token itself becomes
the run's drain token, so an at-least-once replay of `job.finished` stays a
duplicate instead of a 409.
"""

from __future__ import annotations

from contract_server.errors import conflict
from contract_server.util import DRAIN_SECONDS, Json, iso, new_token

FULL = "full"
DRAIN = "drain"


def lease_view(run: Json, token: str, expires: float) -> Json:
    return {
        "job_id": run["job_id"],
        "run_id": run["run_id"],
        "execution_token": token,
        "lease_generation": int(run["generation"]),
        "lease_expires_at": iso(expires),
    }


def issue_lease(run: Json, now: float, seconds: float) -> Json:
    """Next generation of the run's lease, with a fresh opaque token."""
    run["generation"] = int(run["generation"]) + 1
    run["lease_token"] = new_token()
    run["lease_expires"] = now + seconds
    return lease_view(run, run["lease_token"], run["lease_expires"])


def drain_lease(run: Json, now: float) -> Json:
    """The run's drain token (reused while valid), valid 24 h, generation unchanged."""
    if not run.get("drain_token") or float(run.get("drain_expires") or 0) <= now:
        run["drain_token"] = new_token()
        run["drain_expires"] = now + DRAIN_SECONDS
    return lease_view(run, run["drain_token"], float(run["drain_expires"]))


def release_lease(run: Json, now: float, token_was_lease: bool) -> None:
    """End the lease of a finished run; its lease token keeps drain rights."""
    run["lease_expires"] = min(float(run["lease_expires"]), now)
    if token_was_lease:
        run["drain_token"] = run["lease_token"]
        run["drain_expires"] = now + DRAIN_SECONDS


def execution_rights(job: Json, run: Json, token: str | None, worker_id: str, now: float) -> str:
    """FULL or DRAIN for `token` on `run`; 409 lease_* / job_cancelled otherwise."""
    if job.get("worker_id") != worker_id:
        raise conflict("lease_mismatch", "job is pinned to another worker")
    if token and token == run.get("drain_token") and float(run.get("drain_expires") or 0) > now:
        return DRAIN
    if not token or token != run.get("lease_token"):
        raise conflict("lease_mismatch", "execution token is not a lease of this run")
    if job["state"] == "cancelled":
        raise conflict("job_cancelled", "job is cancelled; reconcile for a drain-only token")
    if job.get("current_run_id") != run["run_id"]:
        raise conflict("lease_mismatch", "run is no longer the job's current run")
    if run["finished"] or float(run["lease_expires"]) <= now:
        raise conflict("lease_expired", "lease expired; reconcile to continue")
    return FULL
