"""contact.observed / contact.enriched: evidence, quote and K7 checks, recording.

Checks run in order: every evidence_id uploaded for this job (else
evidence_missing, not recorded), each quote against its evidence text (else
evidence_hash_mismatch), channel fields only from approved hosts (else
host_not_approved), supersedes_observation_id of the same contact and field
(else invalid_input). Accepted observations land on the company-level
canonical contact (`identity.py`) by their change_kind (`history.py`).
"""

from __future__ import annotations

from contract_server import history, identity
from contract_server.channels import channel_status, is_channel, strongest
from contract_server.event_context import Batch, Outcome, rejected
from contract_server.htmltext import quote_found
from contract_server.util import Json, normalize_host, sha256_hex, stamp, url_host

CONTACT_TYPES = frozenset({"contact.observed", "contact.enriched"})
OBSERVATION_FIELDS = (
    "observation_id",
    "field",
    "raw_value",
    "normalized_value",
    "extraction_status",
    "binding",
    "evidence_id",
    "locator",
    "quote",
    "change_kind",
    "supersedes_observation_id",
    "extra_label",
    "source_observed_at",
)


def has_field_audit(event: Json) -> bool:
    payload = event.get("payload")
    return isinstance(payload, dict) and "field_audit" in payload


def _missing_evidence(batch: Batch, payload: Json) -> list[str]:
    wanted = [obs["evidence_id"] for obs in payload["observations"]]
    wanted.append(payload["field_audit"]["evidence_id"])
    job_id = batch.job["job_id"]
    return [
        eid
        for eid in dict.fromkeys(wanted)
        if batch.state["evidence"].get(eid, {}).get("job_id") != job_id
    ]


def quote_matches(batch: Batch, observation: Json) -> bool:
    blobs = batch.stand.blobs
    text = blobs.text(observation["evidence_id"]) or ""
    quote: str = observation["quote"]
    locator: Json = observation["locator"]
    if not quote.strip():
        return False
    if locator["kind"] == "text_span" and locator["text_sha256"] == sha256_hex(
        text.encode("utf-8")
    ):
        return bool(text[locator["start"] : locator["end"]] == quote)
    raw = (blobs.raw(observation["evidence_id"]) or b"").decode("utf-8", errors="replace")
    return quote_found(quote, text, raw)


def host_approved(batch: Batch, observation: Json) -> bool:
    approved = {normalize_host(item["host"]) for item in batch.job["scope"]["approved_hosts"]}
    record = batch.state["evidence"][observation["evidence_id"]]
    return url_host(record["metadata"]["final_url"]) in approved


def stored_observation(batch: Batch, event: Json, observation: Json, status: str | None) -> Json:
    stored: Json = {name: observation.get(name) for name in OBSERVATION_FIELDS}
    stored.update(
        {
            "channel_status": status,
            "event_id": event["event_id"],
            "run_id": event["run_id"],
            "job_id": batch.job["job_id"],
            "observed_at": stamp(event["occurred_at"]),
            "last_confirmed_at": None,
            "superseded_by": None,
            "history": [],
        }
    )
    return stored


def record_contact(batch: Batch, event: Json) -> tuple[str, str | None]:
    payload = event["payload"]
    contact = identity.attach(batch.state, batch.job, payload)
    statuses: list[str | None] = []
    for observation in payload["observations"]:
        status = channel_status(contact["entity_type"], observation)
        statuses.append(status)
        history.add(contact, observation, stored_observation(batch, event, observation, status))
    history.mark_seen(contact, stamp(event["occurred_at"]))
    return contact["canonical_contact_id"], strongest(statuses)


def apply(batch: Batch, event: Json) -> Outcome:
    payload = event["payload"]
    missing = _missing_evidence(batch, payload)
    if missing:
        return rejected("evidence_missing", f"not uploaded: {', '.join(missing)}", record=False)
    for observation in payload["observations"]:
        if not quote_matches(batch, observation):
            detail = f"quote of {observation['observation_id']} not found in its evidence"
            return rejected("evidence_hash_mismatch", detail)
    for observation in payload["observations"]:
        if is_channel(observation["field"]) and not host_approved(batch, observation):
            detail = f"{observation['observation_id']}: evidence host is not approved"
            return rejected("host_not_approved", detail)
    existing = identity.find(batch.state, batch.job, payload)
    problem = history.supersede_error(batch.state, existing, payload["observations"])
    if problem is not None:
        return rejected("invalid_input", problem)
    contact_id, status = record_contact(batch, event)
    return Outcome(
        canonical_contact_id=contact_id, channel_status=status, state_applied=batch.applies
    )
