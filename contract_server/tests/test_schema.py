"""Unit tests of the stand's JSON Schema validator and the OpenAPI helpers."""

from __future__ import annotations

from typing import Any

import pytest

from contract_server import openapi
from contract_server.schema import Schema, format_ok, same, validate


def check(value: Any, schema: Schema) -> list[str]:
    return validate(value, schema, openapi.resolve)


@pytest.mark.parametrize(
    ("value", "schema", "ok"),
    [
        (1, {"type": "integer"}, True),
        (1.0, {"type": "integer"}, True),
        (1.5, {"type": "integer"}, False),
        (True, {"type": "integer"}, False),
        (False, {"type": "number"}, False),
        (None, {"type": ["string", "null"]}, True),
        ("x", {"type": ["string", "null"]}, True),
        (3, {"type": ["string", "null"]}, False),
        ("b", {"enum": ["a", "b"]}, True),
        (1, {"enum": [True]}, False),
        ("1.1", {"const": "1.1"}, True),
        ("1.0", {"const": "1.1"}, False),
        ("abc", {"type": "string", "minLength": 4}, False),
        ("abcdef", {"type": "string", "maxLength": 3}, False),
        (-1, {"type": "integer", "minimum": 0}, False),
        (9, {"type": "integer", "maximum": 8}, False),
        ("a" * 64, {"type": "string", "pattern": "^[a-f0-9]{64}$"}, True),
        ("A" * 64, {"type": "string", "pattern": "^[a-f0-9]{64}$"}, False),
        ([1], {"type": "array", "minItems": 2}, False),
        ([1, 2, 3], {"type": "array", "maxItems": 2}, False),
        (["x", 1], {"type": "array", "items": {"type": "string"}}, False),
    ],
)
def test_keywords(value: Any, schema: Schema, ok: bool) -> None:
    assert (check(value, schema) == []) is ok


def test_objects_required_and_additional_properties() -> None:
    schema: Schema = {
        "type": "object",
        "properties": {"a": {"type": "string"}},
        "required": ["a"],
        "additionalProperties": False,
    }
    assert check({"a": "x"}, schema) == []
    assert check({}, schema) == ["$: missing required property 'a'"]
    assert check({"a": "x", "b": 1}, schema) == ["$: unexpected property 'b'"]
    open_schema = dict(schema, additionalProperties={})
    assert check({"a": "x", "b": 1}, open_schema) == []
    typed = dict(schema, additionalProperties={"type": "integer"})
    assert check({"a": "x", "b": "no"}, typed) == ["$.b: expected integer, got string"]


def test_one_of_needs_exactly_one_branch() -> None:
    schema: Schema = {"oneOf": [{"type": "integer"}, {"type": "number"}]}
    assert check("x", schema)[0] == "$: matches no oneOf branch"
    assert "2 oneOf branches" in check(1, schema)[0]
    assert check(1.5, schema) == []


def test_formats() -> None:
    assert format_ok("https://example.fi/a", "uri")
    assert not format_ok("example.fi/a", "uri")
    assert not format_ok("mailto:x@example.fi", "uri")
    assert format_ok("2026-10-04T12:00:00Z", "date-time")
    assert format_ok("2026-10-04T12:00:00.123+03:00", "date-time")
    assert not format_ok("2026-10-04T12:00:00", "date-time")
    assert not format_ok("2026-13-04T12:00:00Z", "date-time")
    assert not format_ok("04.10.2026", "date-time")


def test_same_keeps_bool_and_number_apart() -> None:
    assert same({"a": [1, "x"]}, {"a": [1, "x"]})
    assert not same(True, 1)
    assert not same([0], [False])


def test_refs_and_nested_paths_in_errors() -> None:
    errors = openapi.check({"code": "x", "detail": "y", "retryable": 1}, "Error")
    assert "$.retryable: expected boolean, got integer" in errors
    assert "$: missing required property 'request_id'" in errors


def test_event_one_of_reports_the_closest_branch() -> None:
    event = {
        "event_id": "e",
        "job_id": "j",
        "run_id": "r",
        "seq": 1,
        "occurred_at": "2026-10-04T12:00:00Z",
        "type": "job.started",
        "payload": {"stage": "teleport", "worker_version": "1"},
    }
    errors = openapi.check(event, "Event")
    assert errors[0] == "$: matches no oneOf branch"
    assert any("$.payload.stage" in error for error in errors[1:])


def test_operation_helpers() -> None:
    assert openapi.operation_for("POST", "/api/collector/jobs/claim") == "claimJobs"
    assert openapi.operation_for("GET", "/api/collector/jobs/abc") == "getJob"
    assert openapi.operation_for("POST", "/api/collector/jobs/abc/events") == "postEvents"
    assert openapi.operation_for("GET", "/_stand/evidence/x") is None
    assert openapi.response_schema("createBatch", 200) == openapi.ref("BatchCreateResponse")
    assert openapi.response_schema("heartbeat", 409) == openapi.ref("Error")
    assert openapi.request_schema("uploadEvidence") == openapi.ref("EvidenceUpload")
    with pytest.raises(KeyError):
        openapi.resolve("#/components/schemas/Nope")
