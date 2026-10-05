"""POST /jobs/{job_id}/events (WorkerBearer): ordered, idempotent event intake.

Envelope errors are 400 (schema_unsupported / invalid_input); a known
event_id with another payload makes the whole request 409
idempotency_conflict before anything is applied. Then each event, in order:
known -> duplicate; seq not next (or after a gap) -> sequence_gap; per-event
schema problems -> field_audit_missing / invalid_input; otherwise the
type's applier decides. Recorded results advance `last_contiguous_seq`.
"""

from __future__ import annotations

import copy

from contract_server import openapi
from contract_server.contacts import CONTACT_TYPES, has_field_audit
from contract_server.context import Request, Stand, validated
from contract_server.errors import ApiError, conflict, invalid
from contract_server.event_apply import apply_event
from contract_server.event_context import Batch, Outcome, rejected
from contract_server.leases import execution_rights
from contract_server.schema import Schema, same
from contract_server.state import bump_revision, job_or_404, run_of_job
from contract_server.util import Json, canonical_hash

EVENT_HEADER: Schema = {
    "type": "object",
    "properties": {
        "event_id": {"type": "string", "minLength": 1, "maxLength": 200},
        "job_id": {"type": "string"},
        "run_id": {"type": "string"},
        "seq": {"type": "integer", "minimum": 0},
    },
    "required": ["event_id", "job_id", "run_id", "seq"],
}


def envelope_schema() -> Schema:
    """EventsRequest with each event reduced to its header (events are checked one by one)."""
    schema = copy.deepcopy(openapi.SCHEMAS["EventsRequest"])
    schema["properties"]["events"]["items"] = EVENT_HEADER
    return schema


ENVELOPE = envelope_schema()


def read_envelope(req: Request) -> Json:
    body = req.json()
    if isinstance(body, dict) and "schema_version" in body:
        if not same(body["schema_version"], "1.1"):
            raise ApiError(400, "schema_unsupported", "events need schema_version 1.1")
    return validated(body, ENVELOPE)


def single_run(stand: Stand, job: Json, events: list[Json]) -> Json:
    if any(event["job_id"] != job["job_id"] for event in events):
        raise invalid("every event must carry the path job_id")
    run_ids = {event["run_id"] for event in events}
    if len(run_ids) != 1:
        raise invalid("one request carries the events of exactly one run")
    run = run_of_job(stand.state, job, run_ids.pop())
    if run is None:
        raise invalid("run_id is not a run of this job")
    return run


def prescan(state: Json, events: list[Json]) -> list[str]:
    """Payload hashes; 409 when a known event_id comes with another payload."""
    digests: list[str] = []
    seen: dict[str, str] = {}
    for event in events:
        digest, event_id = canonical_hash(event), event["event_id"]
        stored = state["events"].get(event_id)
        previous = stored["hash"] if stored is not None else seen.get(event_id)
        if previous is not None and previous != digest:
            raise conflict("idempotency_conflict", f"event {event_id} has another payload")
        seen[event_id] = digest
        digests.append(digest)
    return digests


def result(event: Json, outcome: Outcome, revision: int) -> Json:
    return {
        "event_id": event["event_id"],
        "seq": event["seq"],
        "status": outcome.status,
        "code": outcome.code,
        "canonical_contact_id": outcome.canonical_contact_id,
        "server_revision": revision,
        "state_applied": outcome.state_applied,
        "channel_status": outcome.channel_status,
    }


def evaluate(batch: Batch, event: Json) -> Outcome:
    if event.get("type") in CONTACT_TYPES and not has_field_audit(event):
        return rejected("field_audit_missing", "contact event without payload.field_audit")
    errors = openapi.check(event, "Event")
    if errors:
        return rejected("invalid_input", "; ".join(errors[:3]))
    return apply_event(batch, event)


def store(batch: Batch, event: Json, digest: str, outcome: Outcome) -> Json:
    revision = bump_revision(batch.state)
    batch.run["last_contiguous_seq"] = event["seq"]
    row = result(event, outcome, revision)
    batch.state["events"][event["event_id"]] = {
        "job_id": batch.job["job_id"],
        "run_id": batch.run["run_id"],
        "seq": event["seq"],
        "type": event.get("type"),
        "hash": digest,
        "result": row,
    }
    if outcome.status == "accepted":
        batch.job["last_result_at"] = batch.stand.now()
    else:
        batch.state["rejected"].append(rejection_row(batch, event, outcome))
    return row


def rejection_row(batch: Batch, event: Json, outcome: Outcome) -> Json:
    return {
        "job_id": batch.job["job_id"],
        "run_id": batch.run["run_id"],
        "event_id": event["event_id"],
        "seq": event["seq"],
        "type": event.get("type"),
        "code": outcome.code,
        "detail": outcome.detail,
    }


def process(batch: Batch, event: Json, digest: str) -> Json:
    stored = batch.state["events"].get(event["event_id"])
    if stored is not None:
        return dict(stored["result"], status="duplicate")
    revision = int(batch.state["revision"])
    if batch.gap or event["seq"] != batch.run["last_contiguous_seq"] + 1:
        batch.gap = True
        return result(event, rejected("sequence_gap"), revision)
    outcome = evaluate(batch, event)
    if not outcome.record:
        batch.gap = True
        return result(event, outcome, revision)
    return store(batch, event, digest, outcome)


def handle(stand: Stand, req: Request) -> tuple[int, Json]:
    job = job_or_404(stand.state, req.params["job_id"])
    body = read_envelope(req)
    run = single_run(stand, job, body["events"])
    token = body["execution_token"]
    rights = execution_rights(job, run, token, req.principal, stand.now())
    digests = prescan(stand.state, body["events"])
    batch = Batch(stand, job, run, rights)
    pairs = zip(body["events"], digests, strict=True)
    results = [process(batch, event, digest) for event, digest in pairs]
    return 200, {
        "results": results,
        "last_contiguous_seq": run["last_contiguous_seq"],
        "job_state": job["state"],
        "next_run_scheduled": batch.next_run_scheduled,
    }
