"""POST /jobs/claim (WorkerBearer): atomic claim of up to `max_jobs` queued jobs.

An unfinished current run is re-leased (same run_id and seq, generation+1);
otherwise a new run starts from the previous finished run's checkpoint.
The job is pinned to the first worker that claims it (M1). known_contacts are
the company's contacts accepted from its other jobs (`known.py`).
"""

from __future__ import annotations

from contract_server.context import Request, Stand
from contract_server.errors import invalid
from contract_server.known import known_contacts
from contract_server.leases import issue_lease
from contract_server.state import claimable, current_run
from contract_server.util import Json, iso, new_id

DEFINITION_FIELDS = (
    "batch_id",
    "job_id",
    "company_id",
    "project_id",
    "company_name",
    "seed_urls",
    "scope",
    "policy",
    "participation_status",
    "participation_claim_id",
    "override_reason",
    "rerun_reason",
)


def job_definition(job: Json) -> Json:
    definition: Json = {"schema_version": "1.1"}
    definition.update({name: job[name] for name in DEFINITION_FIELDS})
    return definition


def new_run(state: Json, job: Json, worker_id: str, checkpoint: Json | None, now: float) -> Json:
    run: Json = {
        "run_id": new_id(),
        "job_id": job["job_id"],
        "worker_id": worker_id,
        "generation": 0,
        "lease_token": "",
        "lease_expires": 0.0,
        "drain_token": None,
        "drain_expires": 0.0,
        "last_contiguous_seq": 0,
        "finished": False,
        "checkpoint": checkpoint,
        "result": None,
        "progress": None,
        "attention": [],
        "started_at": now,
        "finished_at": None,
    }
    state["runs"][run["run_id"]] = run
    job["run_ids"].append(run["run_id"])
    job["current_run_id"] = run["run_id"]
    job["continuation"] = "none"
    return run


def claim_job(stand: Stand, job: Json, worker_id: str, now: float) -> Json:
    run = current_run(stand.state, job)
    if run is None or run["finished"]:
        checkpoint = run["result"]["checkpoint"] if run is not None else None
        run = new_run(stand.state, job, worker_id, checkpoint, now)
    lease = issue_lease(run, now, stand.lease_seconds)
    job["state"] = "leased"
    job["worker_id"] = worker_id
    return {
        "job": job_definition(job),
        "lease": lease,
        "checkpoint": run["checkpoint"],
        "routes": [],
        "known_contacts": known_contacts(stand.state, job),
    }


def handle(stand: Stand, req: Request) -> tuple[int, Json]:
    body = req.validated("ClaimRequest")
    if body["worker_id"] != req.principal:
        raise invalid(f"worker_id {body['worker_id']!r} is not the token's worker")
    now = stand.now()
    claimed: list[Json] = []
    for job in stand.state["jobs"].values():
        if len(claimed) >= body["max_jobs"]:
            break
        if claimable(job, req.principal):
            claimed.append(claim_job(stand, job, req.principal, now))
    return 200, {"server_time": iso(now), "jobs": claimed}
