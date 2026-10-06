"""api_client: Event/Locator union codecs -- round trips, wire shape, dispatch."""

from __future__ import annotations

import json
from typing import Any, cast

import pytest

from argus_collector.api_client import contract as api
from argus_collector.api_client.tests import samples

EVENTS: list[api.Event] = [
    samples.contact_observed(),
    samples.job_finished(),
    samples.model_called(),
    samples.job_started(),
    samples.route_recorded(),
    samples.job_progress(),
]
LOCATORS: list[api.Locator] = [
    api.LocatorTextSpan(start=0, end=5, text_sha256=samples.SHA),
    api.LocatorJsonPointer(value="/staff/0/email"),
    api.LocatorDocument(page=2, row=3),
    api.LocatorBbox(page=1, x=10.0, y=20.5, width=100.0, height=12.0),
    api.LocatorDom(value="main > ul > li:nth-child(2)", text_sha256=samples.SHA),
]


@pytest.mark.parametrize("event", EVENTS, ids=lambda event: type(event).__name__)
def test_every_event_kind_round_trips_through_plain_json(event: api.Event) -> None:
    data = api.event_to_json(event)
    assert data == api.to_json(event)
    assert json.loads(json.dumps(data)) == data
    assert data.get("schema_version") in (None, "1.1", "1.2")  # optional since 3.1.0
    parsed = api.event_from_json(json.loads(json.dumps(data)))
    assert parsed == event
    assert type(parsed) is type(event)


def test_contact_observed_wire_shape() -> None:
    data = api.event_to_json(samples.contact_observed())
    assert data["type"] == "contact.observed"
    assert data["seq"] == 3
    payload = data["payload"]
    assert payload["entity_type"] == "person"
    assert payload["relationship"] == "employee"
    observation = payload["observations"][0]
    assert observation["locator"] == {
        "start": 10,
        "end": 26,
        "text_sha256": samples.SHA,
        "kind": "text_span",
    }
    assert observation["extraction_status"] == "confirmed"
    assert observation["binding"] == "card"
    assert observation["raw_value"] == "Matti@Example.fi "
    assert "change_kind" not in observation
    audit = payload["field_audit"]
    assert audit["dropped_contact_fields"] == 0
    assert audit["items"][0]["disposition"] == "mapped"
    assert audit["items"][0]["observation_ids"] == ["obs-1"]


def test_job_finished_wire_shape() -> None:
    payload = api.event_to_json(samples.job_finished())["payload"]
    assert payload["run_result_status"] == "completed"
    assert payload["freshness_summary"] == {
        "reconfirmed": 1,
        "changed": 0,
        "not_seen_in_checked_scope": 0,
        "not_checked": 2,
    }
    assert payload["coverage"]["expected_count"] is None
    assert payload["coverage"]["basis"] == "frontier_exhausted"
    frontier = payload["checkpoint"]["frontier_items"][0]
    assert frontier["filters"] == {"letter": "A"}
    assert frontier["method"] == "browser"
    assert frontier["cursor"] is None
    assert payload["gaps"][0]["reason"] == "captcha"
    assert payload["budget"]["runs_used"] == 1
    assert payload["models"][0]["purpose"] == "card_parsing"
    host = payload["scope"]["approved_hosts"][0]
    assert host == {"host": "example.fi", "basis": "seed", "evidence_id": None}
    assert "restrictions" not in payload["scope"]


def test_model_called_wire_shape() -> None:
    data = api.event_to_json(samples.model_called())
    assert data["type"] == "model.called"
    usage = data["payload"]["usage"]
    assert usage["quantization"] is None
    assert usage["local"] is True
    assert usage["cost_eur"] == 0.0
    assert data["payload"]["source_ids"] == ["src-1"]


@pytest.mark.parametrize("locator", LOCATORS, ids=lambda locator: type(locator).__name__)
def test_locator_union_dispatches_on_kind(locator: api.Locator) -> None:
    data = api.locator_to_json(locator)
    assert data["kind"] == locator.kind
    assert api.locator_from_json(data) == locator
    assert type(api.locator_from_json(data)) is type(locator)


def test_union_from_json_rejects_an_unknown_or_missing_discriminator() -> None:
    with pytest.raises(ValueError, match="unknown type 'job.exploded'"):
        api.event_from_json({**samples.envelope(1), "type": "job.exploded", "payload": {}})
    with pytest.raises(ValueError, match="unknown kind None"):
        api.locator_from_json({"start": 0, "end": 1, "text_sha256": samples.SHA})


def test_union_to_json_rejects_a_non_variant() -> None:
    with pytest.raises(TypeError, match="not a variant: Counts"):
        api.event_to_json(cast(Any, samples.counts()))
