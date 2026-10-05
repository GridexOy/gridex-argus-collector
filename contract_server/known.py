"""ClaimedJob.known_contacts: the company's contacts accepted from its other jobs.

One KnownContact per canonical contact of the job's company that another job
touched (person, department, office, organization_channel; the schema has no
unassigned_channel). `fields` is the stand's documented format:
`{field: [{value, raw_value, observation_id, observed_at}, ...]}` with one
item per distinct normalized value (its latest observation), superseded
observations left out. channel_status is the strongest of the current channel
observations, `inferred` when there is none.
"""

from __future__ import annotations

from contract_server.channels import strongest
from contract_server.identity import observed_value, value_key
from contract_server.util import Json

KNOWN_TYPES = frozenset({"person", "department", "office", "organization_channel"})


def current(contact: Json) -> list[Json]:
    return [obs for obs in contact["observations"].values() if not obs.get("superseded_by")]


def field_item(observation: Json) -> Json:
    return {
        "value": observation["normalized_value"],
        "raw_value": observation["raw_value"],
        "observation_id": observation["observation_id"],
        "observed_at": observation["observed_at"],
    }


def fields_of(observations: list[Json]) -> Json:
    by_field: dict[str, dict[str, Json]] = {}
    for observation in observations:
        field = observation["field"]
        values = by_field.setdefault(field, {})
        key = value_key(field, observed_value(observation))
        previous = values.get(key)
        if previous is None or observation["observed_at"] >= previous["observed_at"]:
            values[key] = field_item(observation)
    return {field: list(values.values()) for field, values in by_field.items()}


def known_contact(contact: Json) -> Json:
    observations = current(contact)
    status = strongest([obs["channel_status"] for obs in observations])
    return {
        "canonical_contact_id": contact["canonical_contact_id"],
        "entity_type": contact["entity_type"],
        "fields": fields_of(observations),
        "last_seen_at": contact["last_seen_at"],
        "channel_status": status or "inferred",
    }


def known_contacts(state: Json, job: Json) -> list[Json]:
    return [
        known_contact(contact)
        for contact in state["contacts"].values()
        if contact["company_id"] == job["company_id"]
        and contact["entity_type"] in KNOWN_TYPES
        and any(job_id != job["job_id"] for job_id in contact["job_ids"])
    ]
