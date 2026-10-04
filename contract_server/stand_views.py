"""Stand-only inspection endpoints under /_stand (SystemBearer, NOT in the contract).

GET /_stand/jobs/{job_id}/contacts and GET /_stand/evidence/{evidence_id}
let the owner and the tests see what the stand accepted.
"""

from __future__ import annotations

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
)
REJECTED_VIEW = ("event_id", "seq", "type", "code", "detail")


def contact_view(contact: Json) -> Json:
    return {
        "canonical_contact_id": contact["canonical_contact_id"],
        "entity_id": contact["entity_id"],
        "entity_type": contact["entity_type"],
        "relationship": contact["relationship"],
        "observations": [
            {name: observation.get(name) for name in OBSERVATION_VIEW}
            for observation in contact["observations"].values()
        ],
    }


def _of_job(rows: list[Json], job_id: str) -> list[Json]:
    return [row for row in rows if row["job_id"] == job_id]


def contacts(stand: Stand, req: Request) -> tuple[int, Json]:
    job = job_or_404(stand.state, req.params["job_id"])
    job_id = job["job_id"]
    rows = [c for c in stand.state["contacts"].values() if c["job_id"] == job_id]
    rejected = _of_job(stand.state["rejected"], job_id)
    return 200, {
        "contacts": [contact_view(contact) for contact in rows],
        "rejected": [{name: row.get(name) for name in REJECTED_VIEW} for row in rejected],
        "model_calls": _of_job(stand.state["model_calls"], job_id),
        "sources": _of_job(stand.state["sources"], job_id),
    }


def evidence(stand: Stand, req: Request) -> tuple[int, Json]:
    evidence_id = req.params["evidence_id"]
    record = stand.state["evidence"].get(evidence_id)
    if record is None:
        raise not_found(f"unknown evidence {evidence_id}")
    return 200, {"metadata": record["metadata"], "text": stand.blobs.text(evidence_id)}
