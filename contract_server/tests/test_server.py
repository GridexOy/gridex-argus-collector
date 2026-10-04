"""Integration tests for the contract_server heartbeat test double (TZ_TANDEM A1)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Iterator
from typing import Any

import pytest

from contract_server import server

TOKEN = "test-token-abc"
WORKER_ID = "worker-main-pc"
VALID_BODY: dict[str, Any] = {
    "worker_id": WORKER_ID,
    "worker_version": "0.4.1.3",
    "schema_versions": ["1.1"],
    "capabilities": {
        "http": True,
        "browser": True,
        "vision": False,
        "model": True,
        "document_formats": [],
        "release_level": "M1",
    },
    "collecting": False,
    "active_jobs": [],
    "outbox_pending": 0,
    "free_job_slots": 1,
    "browser_available": True,
    "model_available": True,
    "acknowledgements": [],
}
# Local-only server: bypass any system proxy (Windows registry proxy
# otherwise answers 127.0.0.1 with 502 Bad Gateway).
DIRECT_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


@pytest.fixture
def running() -> Iterator[server.ContractServer]:
    srv = server.start(port=0, tokens={TOKEN: WORKER_ID})
    try:
        yield srv
    finally:
        srv.shutdown()
        srv.server_close()


def post(
    srv: server.ContractServer,
    body: object,
    token: str | None = TOKEN,
    raw: bytes | None = None,
) -> tuple[int, dict[str, Any]]:
    data = raw if raw is not None else json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    url = server.base_url(srv) + server.HEARTBEAT_PATH
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with DIRECT_OPENER.open(request, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read().decode("utf-8"))


def test_valid_token_gets_heartbeat_response(running: server.ContractServer) -> None:
    status, payload = post(running, VALID_BODY)
    assert status == 200
    assert payload["leases"] == []
    assert payload["commands"] == []
    assert "server_time" in payload


def test_missing_token_is_unauthorized(running: server.ContractServer) -> None:
    status, payload = post(running, VALID_BODY, token=None)
    assert status == 401
    assert payload["code"] == "unauthorized"


def test_unknown_token_is_unauthorized(running: server.ContractServer) -> None:
    status, payload = post(running, VALID_BODY, token="not-a-real-token")
    assert status == 401
    assert payload["code"] == "unauthorized"


def test_unsupported_schema_version_is_rejected(running: server.ContractServer) -> None:
    body = dict(VALID_BODY, schema_versions=["0.9"])
    status, payload = post(running, body)
    assert status == 400
    assert payload["code"] == "schema_unsupported"


def test_malformed_json_body_is_invalid_input(running: server.ContractServer) -> None:
    status, payload = post(running, None, raw=b"{not json")
    assert status == 400
    assert payload["code"] == "invalid_input"


def test_missing_field_is_invalid_input(running: server.ContractServer) -> None:
    body = {key: value for key, value in VALID_BODY.items() if key != "capabilities"}
    status, payload = post(running, body)
    assert status == 400
    assert payload["code"] == "invalid_input"


def test_last_seen_is_recorded(running: server.ContractServer) -> None:
    assert running.registry.seen_at(WORKER_ID) is None
    post(running, VALID_BODY)
    assert running.registry.seen_at(WORKER_ID) is not None
