"""Company-level canonical contacts (TZ_TANDEM B2.7): one contact across jobs.

A person is matched by (company_id, normalized full name) from its `full_name`
observation; a non-person entity by (company_id, entity_type, its first
channel value: normalized email or phone); anything else by (company_id,
job_id, entity_id). Within one job an entity_id keeps the contact it was first
mapped to. `contact_index` holds both kinds of keys -> canonical_contact_id.
"""

from __future__ import annotations

from typing import Any

from contract_server.channels import is_channel
from contract_server.util import Json, canonical_json, iso, new_id


def collapse(text: str) -> str:
    """Casefold and collapse whitespace (the person-name form)."""
    return " ".join(text.split()).casefold()


def is_email(field: str) -> bool:
    return field == "email" or field.startswith("email_")


def field_name(observation: Json) -> str:
    """The field an observation is about: its `extra_label` for an extra field."""
    field = str(observation["field"])
    label = observation.get("extra_label")
    return str(label) if field == "extra" and label else field


def observed_value(observation: Json) -> Any:
    """normalized_value, or raw_value when the worker sent no normalized form."""
    value = observation.get("normalized_value")
    return observation.get("raw_value") if value in (None, "") else value


def value_key(field: str, value: Any) -> str:
    """Comparable form of a value: emails casefolded, phones '+' and digits, text collapsed."""
    if not isinstance(value, str):
        return canonical_json(value)
    if is_channel(field) and is_email(field):
        return value.strip().casefold()
    if is_channel(field):
        digits = "".join(char for char in value if char.isdigit())
        if digits:
            return ("+" if value.strip().startswith("+") else "") + digits
    return collapse(value)


def entity_key(job_id: str, entity_id: str) -> str:
    return f"entity\n{job_id}\n{entity_id}"


def identity_key(company_id: str, entity_type: str, observations: list[Json]) -> str | None:
    """The company-level key of a contact payload, None when it carries nothing to match on."""
    for observation in observations:
        field, raw = observation["field"], observed_value(observation)
        value = value_key(field, raw) if isinstance(raw, str) else ""
        if not value:
            continue
        if entity_type == "person" and field == "full_name":
            return f"person\n{company_id}\n{value}"
        if entity_type != "person" and is_channel(field):
            kind = "email" if is_email(field) else "phone"
            return f"channel\n{company_id}\n{entity_type}\n{kind}:{value}"
    return None


def find(state: Json, job: Json, payload: Json) -> str | None:
    """The existing canonical contact of a contact payload, None when it is new."""
    index = state["contact_index"]
    found: str | None = index.get(entity_key(job["job_id"], payload["entity_id"]))
    if found is None:
        key = identity_key(job["company_id"], payload["entity_type"], payload["observations"])
        found = None if key is None else index.get(key)
    return found


def new_contact(job: Json, payload: Json) -> Json:
    return {
        "canonical_contact_id": new_id(),
        "company_id": job["company_id"],
        "entity_id": payload["entity_id"],
        "entity_type": payload["entity_type"],
        "relationship": payload.get("relationship", "unknown"),
        "job_ids": [],
        "observations": {},
        "aliases": {},
        "history": [],
        "last_seen_at": None,
        "not_seen": None,
    }


def attach(state: Json, job: Json, payload: Json) -> Json:
    """The payload's canonical contact (created when new), mapped and tagged with the job."""
    contact_id = find(state, job, payload)
    if contact_id is None:
        created = new_contact(job, payload)
        contact_id = created["canonical_contact_id"]
        state["contacts"][contact_id] = created
    contact: Json = state["contacts"][contact_id]
    index = state["contact_index"]
    index[entity_key(job["job_id"], payload["entity_id"])] = contact_id
    key = identity_key(job["company_id"], payload["entity_type"], payload["observations"])
    if key is not None:
        index.setdefault(key, contact_id)
    if job["job_id"] not in contact["job_ids"]:
        contact["job_ids"].append(job["job_id"])
    return contact


def _upgrade_contact(state: Json, contact: Json) -> None:
    job_id = contact.pop("job_id", None)
    job = state["jobs"].get(job_id) or {}
    when = iso(float(job.get("last_result_at") or job.get("created_at") or 0))
    contact.update(company_id=job.get("company_id"), job_ids=[job_id] if job_id else [])
    contact.update(aliases={}, history=[], last_seen_at=when, not_seen=None)
    for observation in contact["observations"].values():
        observation.update(job_id=job_id, observed_at=when, history=[])
        observation.update(last_confirmed_at=None, superseded_by=None)
    if job_id:
        key = entity_key(job_id, contact["entity_id"])
        state["contact_index"][key] = contact["canonical_contact_id"]


def upgrade(state: Json) -> None:
    """Contacts saved by an older stand (one per job + entity) get the company-level fields."""
    for contact in state["contacts"].values():
        if "job_ids" not in contact:
            _upgrade_contact(state, contact)
