"""api_client heartbeat: serialization round trips, plus the embedded HTTP double."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from argus_collector.api_client import contract as api
from argus_collector.api_client.tests.fake_argus import FakeArgus
from argus_collector.api_client.tests.samples import capabilities, codec

UNAUTHORIZED = {"code": "unauthorized", "detail": "bad", "retryable": False, "request_id": "r"}


def _sample_request() -> api.HeartbeatRequest:
    return api.HeartbeatRequest(
        worker_id="worker-1",
        worker_version="0.4.1.3",
        schema_versions=["1.1"],
        capabilities=capabilities(),
        collecting=True,
        active_jobs=[api.ActiveLease("job-1", "run-1", "token-xyz", 1)],
        outbox_pending=2,
        free_job_slots=1,
        browser_available=True,
        model_available=True,
        acknowledgements=[api.CommandAck("cmd-1", api.CommandAckStatus.APPLIED, "done")],
    )


def test_heartbeat_request_round_trips_through_json() -> None:
    request = _sample_request()
    data = codec("heartbeat_request_to_json")(request)
    assert data["capabilities"]["release_level"] == "M1"
    assert data["acknowledgements"][0]["status"] == "applied"
    assert codec("heartbeat_request_from_json")(data) == request


def test_heartbeat_response_round_trips_through_json() -> None:
    response = api.HeartbeatResponse(
        server_time="2026-10-04T12:00:00Z",
        leases=[api.LeaseRenewal("job-1", "run-1", api.LeaseRenewalStatus.RENEWED, None)],
        commands=[
            api.Command(
                command_id="cmd-2",
                job_id="job-1",
                action=api.CommandAction.PAUSE,
                state_revision=3,
                policy_patch=api.PolicyPatch(max_pages=50, human_assistance=True),
            )
        ],
    )
    data = api.to_json(response)
    assert data["leases"][0]["status"] == "renewed"
    assert data["leases"][0]["lease_expires_at"] is None
    assert data["commands"][0]["action"] == "pause"
    assert data["commands"][0]["policy_patch"] == {"max_pages": 50, "human_assistance": True}
    assert api.from_json(api.HeartbeatResponse, data) == response


def test_policy_patch_omits_unset_fields() -> None:
    assert api.to_json(api.PolicyPatch()) == {}
    patched = api.PolicyPatch(max_active_seconds=900, cloud_budget_eur=5.0)
    assert api.to_json(patched) == {"max_active_seconds": 900, "cloud_budget_eur": 5.0}


def test_policy_patch_from_json_fills_defaults() -> None:
    patch = api.from_json(api.PolicyPatch, {"max_pages": 10})
    assert patch.max_pages == 10
    assert patch.max_active_seconds == 1800
    assert patch.cloud_budget_eur is None
    assert patch.auto_continue is True


@pytest.fixture
def server() -> Iterator[FakeArgus]:
    srv = FakeArgus().start()
    try:
        yield srv
    finally:
        srv.stop()


def test_heartbeat_over_http_returns_the_parsed_response(server: FakeArgus) -> None:
    server.reply(200, {"server_time": "2026-10-04T00:00:00Z", "leases": [], "commands": []})
    response = api.heartbeat(server.base_url, "good-token", _sample_request(), proxy_mode="direct")
    assert response == api.HeartbeatResponse("2026-10-04T00:00:00Z", [], [])
    assert server.last.path == "/workers/heartbeat"
    assert server.last.headers["authorization"] == "Bearer good-token"
    assert server.last.json()["worker_id"] == "worker-1"


def test_heartbeat_401_raises_api_error_with_the_parsed_body(server: FakeArgus) -> None:
    server.reply(401, UNAUTHORIZED)
    with pytest.raises(api.ApiError) as excinfo:
        api.heartbeat(server.base_url, "wrong-token", _sample_request(), proxy_mode="direct")
    error = excinfo.value
    assert error.status == 401
    assert error.error is not None
    assert error.error.code == "unauthorized"
    assert error.error.retryable is False
