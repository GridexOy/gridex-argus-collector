"""api_client: pure serialization round-trips, plus an embedded HTTP double for repository.py."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest

from argus_collector.api_client import contract, serialization, serialization_patch, service


def _sample_request() -> service.HeartbeatRequest:
    return service.HeartbeatRequest(
        worker_id="worker-1",
        worker_version="0.4.1.3",
        schema_versions=["1.1"],
        capabilities=service.Capabilities(
            http=True,
            browser=True,
            vision=False,
            model=True,
            document_formats=["pdf", "docx"],
            release_level=service.CapabilitiesReleaseLevel.M1,
        ),
        collecting=True,
        active_jobs=[service.ActiveLease("job-1", "run-1", "token-xyz", 1)],
        outbox_pending=2,
        free_job_slots=1,
        browser_available=True,
        model_available=True,
        acknowledgements=[service.CommandAck("cmd-1", service.CommandAckStatus.APPLIED, "done")],
    )


def test_heartbeat_request_round_trips_through_json() -> None:
    request = _sample_request()
    data = serialization.heartbeat_request_to_json(request)
    assert data["capabilities"]["release_level"] == "M1"
    assert data["acknowledgements"][0]["status"] == "applied"
    assert serialization.heartbeat_request_from_json(data) == request


def test_heartbeat_response_round_trips_through_json() -> None:
    response = service.HeartbeatResponse(
        server_time="2026-10-04T12:00:00Z",
        leases=[service.LeaseRenewal("job-1", "run-1", service.LeaseRenewalStatus.RENEWED, None)],
        commands=[
            service.Command(
                command_id="cmd-2",
                job_id="job-1",
                action=service.CommandAction.PAUSE,
                state_revision=3,
                policy_patch=service.PolicyPatch(max_pages=50, human_assistance=True),
            )
        ],
    )
    data = serialization.heartbeat_response_to_json(response)
    assert data["leases"][0]["status"] == "renewed"
    assert data["leases"][0]["lease_expires_at"] is None
    assert data["commands"][0]["action"] == "pause"
    assert data["commands"][0]["policy_patch"] == {"max_pages": 50, "human_assistance": True}
    assert serialization.heartbeat_response_from_json(data) == response


def test_policy_patch_omits_unset_fields() -> None:
    assert serialization_patch.policy_patch_to_json(service.PolicyPatch()) == {}
    patched = service.PolicyPatch(max_active_seconds=900, cloud_budget_eur=5.0)
    assert serialization_patch.policy_patch_to_json(patched) == {
        "max_active_seconds": 900,
        "cloud_budget_eur": 5.0,
    }


def test_policy_patch_from_json_fills_defaults() -> None:
    patch = serialization_patch.policy_patch_from_json({"max_pages": 10})
    assert patch.max_pages == 10
    assert patch.max_active_seconds == 1800
    assert patch.cloud_budget_eur is None
    assert patch.auto_continue is True


class _FakeArgusServer:
    """Minimal stdlib double of /workers/heartbeat; test-only, mirrors fake_model_server.py."""

    def __init__(self, token: str = "good-token") -> None:
        self.token = token
        self.requests: list[dict[str, Any]] = []
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler_class())
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    def start(self) -> _FakeArgusServer:
        self._thread.start()
        return self

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()

    def _send(self, handler: BaseHTTPRequestHandler, code: int, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload).encode("utf-8")
        handler.send_response(code)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(raw)))
        handler.end_headers()
        handler.wfile.write(raw)

    def _handler_class(self) -> type[BaseHTTPRequestHandler]:
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:  # noqa: A002
                return

            def do_POST(self) -> None:  # noqa: N802 - http.server API
                length = int(self.headers.get("Content-Length", "0"))
                owner.requests.append(json.loads(self.rfile.read(length).decode("utf-8")))
                if self.headers.get("Authorization") != f"Bearer {owner.token}":
                    owner._send(
                        self,
                        401,
                        {
                            "code": "unauthorized",
                            "detail": "bad token",
                            "retryable": False,
                            "request_id": "req-1",
                        },
                    )
                    return
                owner._send(
                    self, 200, {"server_time": "2026-10-04T00:00:00Z", "leases": [], "commands": []}
                )

        return Handler


@pytest.fixture
def server() -> Iterator[_FakeArgusServer]:
    srv = _FakeArgusServer().start()
    try:
        yield srv
    finally:
        srv.stop()


def test_heartbeat_over_http_returns_the_parsed_response(server: _FakeArgusServer) -> None:
    response = contract.heartbeat(
        server.base_url, "good-token", _sample_request(), proxy_mode="direct"
    )
    assert response == service.HeartbeatResponse("2026-10-04T00:00:00Z", [], [])
    assert server.requests[-1]["worker_id"] == "worker-1"


def test_heartbeat_401_raises_api_error_with_the_parsed_body(server: _FakeArgusServer) -> None:
    with pytest.raises(contract.ApiError) as excinfo:
        contract.heartbeat(server.base_url, "wrong-token", _sample_request(), proxy_mode="direct")
    error = excinfo.value
    assert error.status == 401
    assert error.error is not None
    assert error.error.code == "unauthorized"
    assert error.error.retryable is False
