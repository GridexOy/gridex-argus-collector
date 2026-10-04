"""Heartbeat basics, bearer auth classes and HTTP-level behaviour of the stand."""

from __future__ import annotations

from contract_server import server
from contract_server.tests import builders
from contract_server.tests.client import SYSTEM_TOKEN, WORKER_ID, WORKER_TOKEN, Client

HEARTBEAT = "/workers/heartbeat"


def test_valid_token_gets_heartbeat_response(client: Client) -> None:
    status, payload = client.post(HEARTBEAT, builders.heartbeat_body())
    assert status == 200
    assert payload["leases"] == []
    assert payload["commands"] == []
    assert payload["server_time"].startswith("2026-10-04T12:00:00")


def test_default_server_keeps_the_seeded_worker_token() -> None:
    srv = server.start(port=0)
    try:
        assert srv.registry.resolve(WORKER_TOKEN) == WORKER_ID
        assert srv.registry.is_system(SYSTEM_TOKEN)
        status, _ = Client(srv).post(HEARTBEAT, builders.heartbeat_body())
        assert status == 200
    finally:
        srv.shutdown()
        srv.server_close()


def test_missing_token_is_unauthorized(client: Client) -> None:
    status, payload = client.post(HEARTBEAT, builders.heartbeat_body(), token=None)
    assert (status, payload["code"]) == (401, "unauthorized")


def test_unknown_token_is_unauthorized(client: Client) -> None:
    status, payload = client.post(HEARTBEAT, builders.heartbeat_body(), token="nope")
    assert (status, payload["code"]) == (401, "unauthorized")


def test_system_token_on_worker_endpoint_is_unauthorized(client: Client) -> None:
    status, payload = client.post(HEARTBEAT, builders.heartbeat_body(), token=SYSTEM_TOKEN)
    assert (status, payload["code"]) == (401, "unauthorized")


def test_worker_token_on_system_endpoint_is_unauthorized(client: Client) -> None:
    status, payload = client.post("/batches", builders.batch_body(), token=WORKER_TOKEN)
    assert (status, payload["code"]) == (401, "unauthorized")
    status, payload = client.get(f"/workers/{WORKER_ID}/status", token=WORKER_TOKEN)
    assert (status, payload["code"]) == (401, "unauthorized")


def test_revoked_worker_is_forbidden(client: Client) -> None:
    client.srv.registry.revoke(WORKER_ID)
    status, payload = client.post(HEARTBEAT, builders.heartbeat_body())
    assert (status, payload["code"]) == (403, "worker_revoked")


def test_unsupported_schema_version_is_rejected(client: Client) -> None:
    body = dict(builders.heartbeat_body(), schema_versions=["0.9"])
    status, payload = client.post(HEARTBEAT, body)
    assert (status, payload["code"]) == (400, "schema_unsupported")


def test_malformed_json_body_is_invalid_input(client: Client) -> None:
    headers = {"Content-Type": "application/json"}
    status, payload = client.request("POST", HEARTBEAT, b"{not json", WORKER_TOKEN, headers)
    assert (status, payload["code"]) == (400, "invalid_input")


def test_missing_field_is_invalid_input(client: Client) -> None:
    body = builders.heartbeat_body()
    del body["capabilities"]
    status, payload = client.post(HEARTBEAT, body)
    assert (status, payload["code"]) == (400, "invalid_input")
    assert "capabilities" in payload["detail"]


def test_extra_field_is_invalid_input(client: Client) -> None:
    body = dict(builders.heartbeat_body(), surprise=1)
    status, payload = client.post(HEARTBEAT, body)
    assert (status, payload["code"]) == (400, "invalid_input")


def test_last_seen_is_recorded(client: Client) -> None:
    assert client.srv.registry.seen_at(WORKER_ID) is None
    client.post(HEARTBEAT, builders.heartbeat_body())
    assert client.srv.registry.seen_at(WORKER_ID) is not None


def test_unknown_path_and_wrong_method(client: Client) -> None:
    status, payload = client.get("/nothing-here")
    assert (status, payload["code"]) == (404, "invalid_input")
    status, payload = client.get(HEARTBEAT)
    assert status == 405
    assert payload["code"] == "invalid_input"


def test_unknown_job_batch_worker_are_404(client: Client) -> None:
    for path in ("/jobs/missing", "/batches/missing", "/workers/missing/status"):
        status, payload = client.get(path)
        assert (status, payload["code"]) == (404, "invalid_input"), path


def test_error_bodies_carry_a_request_id(client: Client) -> None:
    _, first = client.post(HEARTBEAT, builders.heartbeat_body(), token=None)
    _, second = client.post(HEARTBEAT, builders.heartbeat_body(), token=None)
    assert first["request_id"] != second["request_id"]
    assert first["retryable"] is False
