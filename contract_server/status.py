"""GET /jobs/{id}, GET /batches/{id}, GET /workers/{id}/status (SystemBearer)."""

from __future__ import annotations

from contract_server.context import Request, Stand
from contract_server.errors import not_found
from contract_server.state import claimable, job_or_404
from contract_server.util import OFFLINE_AFTER_SECONDS, Json, iso_or_none

DEFAULT_COVERAGE: Json = {
    "frontier_status": "not_started",
    "confirmation": "unverified",
    "basis": "unknown",
    "scope_description": "",
    "expected_count": None,
    "found_count": 0,
    "gap_count": 0,
    "evidence_ids": [],
}
BUDGET_FIELDS = (
    "campaign_active_seconds",
    "campaign_pages",
    "campaign_states",
    "campaign_browser_actions",
    "campaign_cloud_eur",
)
DEFAULT_CAPABILITIES: Json = {
    "http": False,
    "browser": False,
    "vision": False,
    "model": False,
    "document_formats": [],
    "release_level": "M1",
}


def transport_state(stand: Stand, worker_id: str | None) -> str:
    if worker_id is None:
        return "synced"
    worker = stand.state["workers"].get(worker_id)
    if worker is None or stand.now() - float(worker["last_seen"]) > OFFLINE_AFTER_SECONDS:
        return "offline"
    return "syncing" if worker["outbox_pending"] > 0 else "synced"


def job_observation_ids(contact: Json, job_id: str) -> set[str]:
    """Observation ids of one job on a contact: stored rows and reconfirmation aliases."""
    rows = {**contact["observations"], **contact["aliases"]}
    return {oid for oid, row in rows.items() if row["job_id"] == job_id}


def job_counts(stand: Stand, job: Json, gaps: list[Json]) -> Json:
    state, job_id = stand.state, job["job_id"]
    contacts = [c for c in state["contacts"].values() if job_id in c["job_ids"]]
    kinds = [c["entity_type"] for c in contacts]
    snapshot = job.get("counts_snapshot") or {}
    worker = state["workers"].get(job["worker_id"] or "") or {}
    return {
        "persons": kinds.count("person"),
        "organization_channels": kinds.count("organization_channel"),
        "other_entities": len(kinds) - kinds.count("person") - kinds.count("organization_channel"),
        "observations": sum(len(job_observation_ids(c, job_id)) for c in contacts),
        "pages_processed": sum(
            1 for s in state["sources"] if s["job_id"] == job_id and s["type"] == "source.processed"
        ),
        "browser_actions": int(snapshot.get("browser_actions", 0)),
        "evidence_count": sum(1 for e in state["evidence"].values() if e["job_id"] == job_id),
        "gaps": len(gaps),
        "outbox_pending": int(worker.get("outbox_pending", 0)),
        "states_processed": int(snapshot.get("states_processed", 0)),
    }


def job_status(stand: Stand, job: Json) -> Json:
    runs = [stand.state["runs"][run_id] for run_id in job["run_ids"]]
    finished = [run["result"] for run in runs if run["finished"]]
    last = finished[-1] if finished else None
    progress = next((run["progress"] for run in reversed(runs) if run["progress"]), None)
    gaps: list[Json] = last["gaps"] if last else []
    coverage = last["coverage"] if last else (progress or {}).get("coverage", DEFAULT_COVERAGE)
    budget = last["budget"] if last else dict.fromkeys(BUDGET_FIELDS, 0) | {"runs_used": len(runs)}
    continuation = job["continuation"]
    if job["state"] == "needs_attention":
        continuation = "waiting_attention"
    return {
        "job_id": job["job_id"],
        "batch_id": job["batch_id"],
        "company_id": job["company_id"],
        "state": job["state"],
        "state_revision": job["state_revision"],
        "current_run_id": job["current_run_id"],
        "stage": job["stage"],
        "counts": job_counts(stand, job, gaps),
        "coverage": coverage,
        "transport_state": transport_state(stand, job["worker_id"]),
        "gaps": gaps,
        "continuation": continuation,
        "runs_completed": len(finished),
        "last_result_at": iso_or_none(job["last_result_at"]),
        "budget": budget,
        "completion_reason": last["completion_reason"] if last else None,
        "project_id": job["project_id"],
    }


def worker_status(stand: Stand, worker_id: str) -> Json:
    record = stand.state["workers"].get(worker_id) or {}
    last_seen = record.get("last_seen")
    connected = last_seen is not None and stand.now() - last_seen <= OFFLINE_AFTER_SECONDS
    queued = sum(1 for job in stand.state["jobs"].values() if claimable(job, worker_id))
    outbox = int(record.get("outbox_pending", 0))
    return {
        "worker_id": worker_id,
        "connected": connected,
        "collecting": bool(record.get("collecting", False)),
        "last_seen_at": iso_or_none(last_seen),
        "worker_version": record.get("worker_version", ""),
        "capabilities": record.get("capabilities", DEFAULT_CAPABILITIES),
        "outbox_pending": outbox,
        "active_job_ids": list(record.get("active_job_ids", [])),
        "browser_available": bool(record.get("browser_available", False)),
        "model_available": bool(record.get("model_available", False)),
        "queued_jobs": queued,
        "transport_state": "offline" if not connected else ("syncing" if outbox else "synced"),
    }


def get_job(stand: Stand, req: Request) -> tuple[int, Json]:
    return 200, job_status(stand, job_or_404(stand.state, req.params["job_id"]))


def get_batch(stand: Stand, req: Request) -> tuple[int, Json]:
    batch = stand.state["batches"].get(req.params["batch_id"])
    if batch is None:
        raise not_found(f"unknown batch {req.params['batch_id']}")
    jobs = [job_status(stand, stand.state["jobs"][job_id]) for job_id in batch["job_ids"]]
    return 200, {"batch_id": batch["batch_id"], "jobs": jobs}


def get_worker(stand: Stand, req: Request) -> tuple[int, Json]:
    worker_id = req.params["worker_id"]
    if worker_id not in stand.state["workers"] and not stand.registry.known_worker(worker_id):
        raise not_found(f"unknown worker {worker_id}")
    return 200, worker_status(stand, worker_id)
