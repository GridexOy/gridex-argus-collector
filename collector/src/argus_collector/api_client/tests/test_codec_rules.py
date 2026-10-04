"""api_client codec rules: generic to_json/from_json, const, nullable refs, optional fields."""

from __future__ import annotations

import dataclasses
import json
from typing import Any

import pytest

from argus_collector.api_client import contract as api
from argus_collector.api_client.tests import samples, wire_samples
from argus_collector.api_client.tests.samples import codec


def _through_text(data: dict[str, Any]) -> dict[str, Any]:
    """What an outbox row gives back: the JSON object after a trip through text."""
    loaded: dict[str, Any] = json.loads(json.dumps(data))
    return loaded


def test_generic_codec_round_trips_job_definition_claimed_job_and_evidence() -> None:
    job = wire_samples.job_definition()
    assert api.from_json(api.JobDefinition, _through_text(api.to_json(job))) == job
    claimed = wire_samples.claimed_job(samples.checkpoint())
    restored = api.from_json(api.ClaimedJob, _through_text(api.to_json(claimed)))
    assert restored == claimed
    assert isinstance(restored.checkpoint, api.Checkpoint)
    metadata = samples.evidence_metadata(b"<html></html>")
    assert api.from_json(api.EvidenceMetadata, _through_text(api.to_json(metadata))) == metadata


def test_generic_to_json_with_event_from_json_round_trips_a_contact_event() -> None:
    event = samples.contact_observed()
    assert api.event_from_json(_through_text(api.to_json(event))) == event


def test_generic_codec_rejects_types_it_does_not_know() -> None:
    with pytest.raises(TypeError, match="not a generated api_client type: dict"):
        api.to_json({"a": 1})
    with pytest.raises(TypeError, match="not a generated api_client type: int"):
        api.from_json(int, {})


def test_claim_response_wire_example_survives_a_parse_and_a_dump() -> None:
    response = api.from_json(api.ClaimResponse, wire_samples.CLAIM_RESPONSE)
    job = response.jobs[0]
    assert job.checkpoint is None
    assert job.job.project_id is None
    assert job.job.policy.max_runs == 3
    assert job.job.policy.auto_continue is True
    assert job.known_contacts[0].fields == {"email": "matti@example.fi", "phone": None}
    assert api.to_json(response) == wire_samples.CLAIM_RESPONSE


def test_a_missing_const_takes_the_const_value() -> None:
    data = api.to_json(samples.job_started())
    del data["schema_version"]
    assert api.event_from_json(data) == samples.job_started()
    audit = api.from_json(api.FieldAudit, {"evidence_id": "evd-1", "items": []})
    assert audit.dropped_contact_fields == 0


@pytest.mark.parametrize(
    ("kind", "data", "message"),
    [
        (api.FieldAudit, {"evidence_id": "e", "items": [], "dropped_contact_fields": 2}, "got 2"),
        (api.FieldAudit, {"evidence_id": "e", "items": [], "dropped_contact_fields": False}, ""),
        (api.LocatorDom, {"kind": "bbox", "value": "x", "text_sha256": "y"}, "kind"),
        (api.EventsRequest, {"schema_version": "1.0", "execution_token": "t", "events": []}, ""),
    ],
)
def test_a_different_const_raises_value_error(kind: type[Any], data: Any, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        api.from_json(kind, data)


def test_a_variant_codec_rejects_another_variants_discriminator() -> None:
    data = {**api.to_json(samples.job_started()), "type": "job.finished"}
    with pytest.raises(ValueError, match="type: expected 'job.started'"):
        codec("job_started_event_from_json")(data)


def test_const_fields_are_always_written() -> None:
    request = api.EventsRequest(execution_token="exec-1", events=[samples.job_started()])
    data = api.to_json(request)
    assert data["schema_version"] == "1.1"
    assert data["events"][0]["type"] == "job.started"
    pointer = api.to_json(api.LocatorJsonPointer(value="/x"))
    assert pointer == {"value": "/x", "kind": "json_pointer"}
    assert api.to_json(api.FieldAudit("evd-1", []))["dropped_contact_fields"] == 0


def test_nullable_refs_round_trip_as_null_or_value() -> None:
    bare = wire_samples.claimed_job(None)
    assert api.to_json(bare)["checkpoint"] is None
    assert api.from_json(api.ClaimedJob, api.to_json(bare)) == bare
    accepted = api.EventResultStatus.ACCEPTED
    for status in (None, api.ChannelStatus.PUBLISHED_DIRECT):
        result = api.EventResult("ev-1", 1, accepted, None, None, 0, True, status)
        data = api.to_json(result)
        assert data["channel_status"] == (status.value if status else None)
        assert api.from_json(api.EventResult, data) == result


def test_optional_fields_are_omitted_until_set() -> None:
    observation = samples.observation()
    optional = {"source_observed_at", "change_kind", "supersedes_observation_id", "extra_label"}
    assert not optional & api.to_json(observation).keys()
    changed = dataclasses.replace(
        observation, change_kind=api.ObservationChangeKind.CHANGED, supersedes_observation_id="o-0"
    )
    data = api.to_json(changed)
    assert data["change_kind"] == "changed"
    assert data["supersedes_observation_id"] == "o-0"
    assert api.from_json(api.Observation, data) == changed
    assert api.to_json(api.LocatorDocument(page=1)) == {"page": 1, "kind": "document"}
    policy = api.to_json(wire_samples.job_definition().policy)
    assert policy["auto_continue"] is False
    assert not {"max_runs", "max_campaign_active_seconds"} & policy.keys()
