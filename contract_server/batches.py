"""POST /batches (SystemBearer): idempotent batch creation, R8 and rerun checks."""

from __future__ import annotations

from typing import Any

from contract_server.context import Request, Stand
from contract_server.errors import conflict, unprocessable
from contract_server.util import Json, caller_key, canonical_hash, new_id

CLAIM_REQUIRED = ("confirmed", "strong_historical")


def _filled(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _label(index: int, company: Json) -> str:
    return f"companies[{index}] ({company['company_id']})"


def check_participation(companies: list[Json]) -> None:
    """R8: confirmed/strong_historical need a claim id, owner_override a reason."""
    for index, company in enumerate(companies):
        status = company["participation_status"]
        if status in CLAIM_REQUIRED and not _filled(company["participation_claim_id"]):
            raise unprocessable(
                "participation_not_confirmed",
                f"{_label(index, company)}: {status} requires participation_claim_id",
            )
        if status == "owner_override" and not _filled(company["override_reason"]):
            raise unprocessable(
                "participation_not_confirmed",
                f"{_label(index, company)}: owner_override requires override_reason",
            )


def check_reruns(state: Json, companies: list[Json]) -> None:
    """A company (company_id + project_id) that already has a job needs rerun_reason."""
    seen = {(job["company_id"], job["project_id"]) for job in state["jobs"].values()}
    for index, company in enumerate(companies):
        key = (company["company_id"], company["project_id"])
        if key in seen and not _filled(company["rerun_reason"]):
            raise unprocessable(
                "invalid_input",
                f"{_label(index, company)} already has a job in project "
                f"{company['project_id']}; rerun_reason is required",
            )
        seen.add(key)


def new_job(company: Json, batch_id: str, now: float) -> Json:
    job: Json = dict(company)
    job.update(
        {
            "job_id": new_id(),
            "batch_id": batch_id,
            "state": "queued",
            "state_revision": 0,
            "stage": None,
            "worker_id": None,
            "current_run_id": None,
            "run_ids": [],
            "continuation": "none",
            "counts_snapshot": None,
            "created_at": now,
            "last_result_at": None,
        }
    )
    return job


def create_jobs(stand: Stand, companies: list[Json]) -> Json:
    batch_id, now = new_id(), stand.now()
    jobs = [new_job(company, batch_id, now) for company in companies]
    for job in jobs:
        stand.state["jobs"][job["job_id"]] = job
    stand.state["batches"][batch_id] = {
        "batch_id": batch_id,
        "job_ids": [job["job_id"] for job in jobs],
        "created_at": now,
    }
    return {
        "batch_id": batch_id,
        "jobs": [{"job_id": job["job_id"], "company_id": job["company_id"]} for job in jobs],
    }


def create(stand: Stand, req: Request) -> tuple[int, Json]:
    body = req.validated("BatchCreateRequest")
    key = f"{caller_key(req.principal)}\n{body['client_request_id']}"
    digest = canonical_hash(body)
    known = stand.state["batch_keys"].get(key)
    if known is not None:
        if known["hash"] != digest:
            raise conflict("idempotency_conflict", "client_request_id reused with another payload")
        replay: Json = known["response"]
        return 200, replay
    check_participation(body["companies"])
    check_reruns(stand.state, body["companies"])
    response = create_jobs(stand, body["companies"])
    stand.state["batch_keys"][key] = {"hash": digest, "response": response}
    return 201, response
