"""POST /jobs/{job_id}/evidence (WorkerBearer, multipart: `metadata` + `file`).

Checks ownership (400), the execution token (409), idempotency by
evidence_id (200 duplicate / 409), size by source_kind (413) and hashes
(422), then stores the bytes inertly plus the text used for quote checks.
"""

from __future__ import annotations

import json

from contract_server import multipart
from contract_server.context import Request, Stand, validated
from contract_server.errors import ApiError, conflict, invalid
from contract_server.htmltext import derive_text
from contract_server.leases import execution_rights
from contract_server.state import job_or_404, run_of_job
from contract_server.util import Json, new_id, sha256_hex

MIB = 1024 * 1024
SIZE_LIMITS = {
    "http_html": 25 * MIB,
    "browser_dom": 25 * MIB,
    "json_response": 25 * MIB,
    "embedded_data": 25 * MIB,
    "document": 50 * MIB,
    "checkpoint": 50 * MIB,
    "screenshot": 10 * MIB,
    "ocr": 10 * MIB,
}


def read_upload(req: Request) -> tuple[Json, bytes]:
    parts = multipart.parse(req.header("content-type") or "", req.body)
    if "metadata" not in parts or "file" not in parts:
        raise invalid("multipart body needs the parts 'metadata' and 'file'")
    try:
        metadata = json.loads(parts["metadata"].data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise invalid(f"metadata is not JSON: {exc}") from exc
    return validated(metadata, "EvidenceMetadata"), parts["file"].data


def owned_run(stand: Stand, job: Json, metadata: Json) -> Json:
    if metadata["job_id"] != job["job_id"]:
        raise invalid("metadata.job_id does not match the path")
    if metadata["company_id"] != job["company_id"]:
        raise invalid("metadata.company_id is not the job's company")
    run = run_of_job(stand.state, job, metadata["run_id"])
    if run is None:
        raise invalid("metadata.run_id is not a run of this job")
    return run


def check_size(metadata: Json, data: bytes) -> None:
    limit = SIZE_LIMITS[metadata["source_kind"]]
    if len(data) > limit or int(metadata["byte_length"]) > limit:
        raise ApiError(
            413, "payload_too_large", f"{metadata['source_kind']} is limited to {limit} bytes"
        )


def check_hashes(metadata: Json, data: bytes) -> None:
    if sha256_hex(data) != metadata["sha256"] or len(data) != metadata["byte_length"]:
        raise ApiError(422, "evidence_hash_mismatch", "file does not match sha256/byte_length")
    text = metadata.get("canonical_text")
    expected = metadata.get("canonical_text_sha256")
    if expected is not None and text is not None and sha256_hex(text.encode("utf-8")) != expected:
        raise ApiError(422, "evidence_hash_mismatch", "canonical_text does not match its sha256")


def replay(known: Json, metadata: Json) -> tuple[int, Json]:
    if known["sha256"] != metadata["sha256"] or known["job_id"] != metadata["job_id"]:
        raise conflict("idempotency_conflict", "evidence_id was uploaded with other content")
    return 200, response(known, "duplicate")


def response(record: Json, status: str) -> Json:
    return {
        "evidence_id": record["evidence_id"],
        "snapshot_id": record["snapshot_id"],
        "status": status,
        "sha256": record["sha256"],
    }


def store(stand: Stand, metadata: Json, data: bytes) -> Json:
    text = metadata.get("canonical_text")
    if text is None:
        text = derive_text(data, metadata["mime_type"], metadata["source_kind"])
    stand.blobs.put(metadata["evidence_id"], data, text)
    kept = {key: value for key, value in metadata.items() if key != "canonical_text"}
    record: Json = {
        "evidence_id": metadata["evidence_id"],
        "job_id": metadata["job_id"],
        "run_id": metadata["run_id"],
        "sha256": metadata["sha256"],
        "snapshot_id": None if metadata["source_kind"] == "checkpoint" else new_id(),
        "uploaded_at": stand.now(),
        "metadata": kept,
    }
    stand.state["evidence"][record["evidence_id"]] = record
    return record


def handle(stand: Stand, req: Request) -> tuple[int, Json]:
    job = job_or_404(stand.state, req.params["job_id"])
    metadata, data = read_upload(req)
    token = req.header("x-execution-token")
    if not token:
        raise invalid("X-Execution-Token header is required")
    run = owned_run(stand, job, metadata)
    execution_rights(job, run, token, req.principal, stand.now())
    known = stand.state["evidence"].get(metadata["evidence_id"])
    if known is not None:
        return replay(known, metadata)
    check_size(metadata, data)
    check_hashes(metadata, data)
    return 201, response(store(stand, metadata, data), "accepted")
