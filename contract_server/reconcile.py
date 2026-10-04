"""POST /jobs/{job_id}/reconcile (WorkerBearer): resume or drain-only.

Only the pinned worker, for a run of this job (else 409 lease_mismatch).
The unfinished current run of a live job gets a new lease generation
(mode resume, run and seq preserved); a cancelled/terminal job, a finished
run or an old run gets a drain-only token for that run (mode drain_only).
"""

from __future__ import annotations

from contract_server.context import Request, Stand
from contract_server.errors import conflict
from contract_server.leases import drain_lease, issue_lease
from contract_server.state import is_terminal, job_or_404, run_of_job
from contract_server.util import Json


def resumable(job: Json, run: Json) -> bool:
    return job["current_run_id"] == run["run_id"] and not run["finished"] and not is_terminal(job)


def known_ids(collection: Json, ids: list[str], job_id: str) -> list[str]:
    return [item for item in dict.fromkeys(ids) if collection.get(item, {}).get("job_id") == job_id]


def handle(stand: Stand, req: Request) -> tuple[int, Json]:
    body = req.validated("ReconcileRequest")
    job = job_or_404(stand.state, req.params["job_id"])
    run = run_of_job(stand.state, job, body["run_id"])
    worker_id = body["worker_id"]
    if run is None or worker_id != req.principal or job["worker_id"] != worker_id:
        raise conflict("lease_mismatch", "only the pinned worker can reconcile a run of this job")
    now = stand.now()
    if resumable(job, run):
        mode, lease = "resume", issue_lease(run, now, stand.lease_seconds)
        if job["state"] == "queued":
            job["state"] = "leased"
    else:
        mode, lease = "drain_only", drain_lease(run, now)
    pending_evidence = body["pending_evidence_ids"]
    accepted_evidence = known_ids(stand.state["evidence"], pending_evidence, job["job_id"])
    return 200, {
        "mode": mode,
        "lease": lease,
        "accepted_event_ids": known_ids(
            stand.state["events"], body["pending_event_ids"], job["job_id"]
        ),
        "accepted_evidence_ids": accepted_evidence,
        "missing_evidence_ids": [
            item for item in dict.fromkeys(pending_evidence) if item not in accepted_evidence
        ],
        "last_contiguous_seq": run["last_contiguous_seq"],
        "job_state": job["state"],
    }
