"""contact.observed / contact.enriched: evidence, quote and K7 checks, recording.

Checks run in order: every evidence_id uploaded for this job (else
evidence_missing, not recorded), each quote against its evidence text (else
evidence_hash_mismatch), channel fields only from approved hosts (else
host_not_approved). Accepted observations land on one canonical contact per
(job_id, entity_id); a repeated observation_id adds nothing.
"""

from __future__ import annotations

from contract_server.channels import channel_status, is_channel, strongest
from contract_server.event_context import Batch, Outcome, rejected
from contract_server.htmltext import quote_found
from contract_server.util import Json, new_id, normalize_host, sha256_hex, url_host

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


def _contact(batch: Batch, payload: Json) -> Json:
    key = f"{batch.job['job_id']}\n{payload['entity_id']}"
    contact_id = batch.state["contact_index"].get(key)
    if contact_id is None:
        contact_id = new_id()
        batch.state["contact_index"][key] = contact_id
        batch.state["contacts"][contact_id] = {
            "canonical_contact_id": contact_id,
            "job_id": batch.job["job_id"],
            "entity_id": payload["entity_id"],
            "entity_type": payload["entity_type"],
            "relationship": payload.get("relationship", "unknown"),
            "observations": {},
        }
    contact: Json = batch.state["contacts"][contact_id]
    return contact


def record_contact(batch: Batch, event: Json) -> tuple[str, str | None]:
    payload = event["payload"]
    contact = _contact(batch, payload)
    statuses: list[str | None] = []
    for observation in payload["observations"]:
        status = channel_status(contact["entity_type"], observation)
        statuses.append(status)
        if observation["observation_id"] in contact["observations"]:
            continue
        stored: Json = {name: observation.get(name) for name in OBSERVATION_FIELDS}
        stored.update(
            {"channel_status": status, "event_id": event["event_id"], "run_id": event["run_id"]}
        )
        contact["observations"][observation["observation_id"]] = stored
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
    contact_id, status = record_contact(batch, event)
    return Outcome(
        canonical_contact_id=contact_id, channel_status=status, state_applied=batch.applies
    )
