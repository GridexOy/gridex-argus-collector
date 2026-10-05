"""Stand-only inspection endpoints under /_stand (SystemBearer, NOT in the contract).

GET /_stand/jobs/{job_id}/contacts, GET /_stand/companies/{company_id}/contacts
and GET /_stand/evidence/{evidence_id} let the owner and the tests see what
the stand accepted. Contacts are company-level canonical contacts.
"""

from __future__ import annotations

from contract_server import freshness
from contract_server.context import Request, Stand
from contract_server.errors import not_found
from contract_server.state import job_or_404
from contract_server.util import Json

OBSERVATION_VIEW = (
    "observation_id",
    "field",
    "raw_value",
    "normalized_value",
    "extraction_status",
    "binding",
    "channel_status",
    "evidence_id",
    "quote",
    "change_kind",
    "supersedes_observation_id",
    "job_id",
    "run_id",
    "observed_at",
    "last_confirmed_at",
    "superseded_by",
    "history",
)
CONTACT_VIEW = (
    "canonical_contact_id",
    "company_id",
    "entity_id",
    "entity_type",
    "relationship",
    "job_ids",
    "last_seen_at",
    "not_seen",
    "history",
)
REJECTED_VIEW = ("event_id", "seq", "type", "code", "detail")
RUN_FRESHNESS_VIEW = ("freshness_summary", "freshness_counted", "freshness_mismatch")


def contact_view(contact: Json) -> Json:
    view: Json = {name: contact.get(name) for name in CONTACT_VIEW}
    view["observations"] = [
        {name: observation.get(name) for name in OBSERVATION_VIEW}
        for observation in contact["observations"].values()
    ]
    return view


def _of_job(rows: list[Json], job_id: str) -> list[Json]:
    return [row for row in rows if row["job_id"] == job_id]


def freshness_checks(state: Json, job_id: str) -> list[Json]:
    """Every accepted contact.freshness check of the job, tagged with run and event."""
    return [
        dict(check, run_id=row["run_id"], event_id=row["event_id"])
        for row in _of_job(state["records"], job_id)
        if row["type"] == freshness.TYPE
        for check in row["payload"]["checks"]
    ]


def freshness_runs(state: Json, job: Json) -> list[Json]:
    runs = [state["runs"][run_id] for run_id in job["run_ids"]]
    return [
        dict({name: run.get(name) for name in RUN_FRESHNESS_VIEW}, run_id=run["run_id"])
        for run in runs
        if run["finished"]
    ]


def contacts(stand: Stand, req: Request) -> tuple[int, Json]:
    state = stand.state
    job = job_or_404(state, req.params["job_id"])
    job_id = job["job_id"]
    rows = [c for c in state["contacts"].values() if job_id in c["job_ids"]]
    rejected = _of_job(state["rejected"], job_id)
    return 200, {
        "contacts": [contact_view(contact) for contact in rows],
        "rejected": [{name: row.get(name) for name in REJECTED_VIEW} for row in rejected],
        "model_calls": _of_job(state["model_calls"], job_id),
        "sources": _of_job(state["sources"], job_id),
        "freshness": freshness_checks(state, job_id),
        "freshness_runs": freshness_runs(state, job),
    }


def company_contacts(stand: Stand, req: Request) -> tuple[int, Json]:
    company_id = req.params["company_id"]
    jobs = [job for job in stand.state["jobs"].values() if job["company_id"] == company_id]
    if not jobs:
        raise not_found(f"unknown company {company_id}")
    rows = [c for c in stand.state["contacts"].values() if c["company_id"] == company_id]
    return 200, {
        "company_id": company_id,
        "job_ids": [job["job_id"] for job in jobs],
        "contacts": [contact_view(contact) for contact in rows],
    }


def evidence(stand: Stand, req: Request) -> tuple[int, Json]:
    evidence_id = req.params["evidence_id"]
    record = stand.state["evidence"].get(evidence_id)
    if record is None:
        raise not_found(f"unknown evidence {evidence_id}")
    return 200, {"metadata": record["metadata"], "text": stand.blobs.text(evidence_id)}
