"""HTTP client of the tests: real requests, every response checked against the contract."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
import uuid
from typing import Any

from contract_server import openapi, server
from contract_server.util import Json

API = "/api/collector"
WORKER_TOKEN = "test-token-abc"
WORKER_ID = "worker-main-pc"
WORKER2_TOKEN = "token-two"
WORKER2_ID = "worker-two"
SYSTEM_TOKEN = "system-token-xyz"
# Local-only server: bypass any system proxy (Windows registry proxy
# otherwise answers 127.0.0.1 with 502 Bad Gateway).
DIRECT_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def assert_contract(method: str, path: str, status: int, payload: Any) -> None:
    """2xx bodies match the operation's response schema, everything else `Error`."""
    operation_id = openapi.operation_for(method, path)
    if operation_id is None and path.startswith("/_stand/") and status == 200:
        assert isinstance(payload, dict)
        return
    if operation_id is not None and status in (200, 201):
        schema = openapi.response_schema(operation_id, status)
    else:
        schema = openapi.ref("Error")
    errors = openapi.check(payload, schema)
    assert not errors, f"{method} {path} -> {status}: {errors}"


def full_path(path: str) -> str:
    return path if path.startswith("/_stand/") or path.startswith(API) else API + path


class Client:
    def __init__(self, srv: server.ContractServer) -> None:
        self.srv = srv
        self.base = server.base_url(srv)

    def request(
        self,
        method: str,
        path: str,
        data: bytes | None = None,
        token: str | None = WORKER_TOKEN,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, Json]:
        path = full_path(path)
        all_headers = dict(headers or {})
        if token is not None:
            all_headers["Authorization"] = f"Bearer {token}"
        request = urllib.request.Request(
            self.base + path, data=data, headers=all_headers, method=method
        )
        try:
            with DIRECT_OPENER.open(request, timeout=10) as resp:
                status, raw = int(resp.status), resp.read()
        except urllib.error.HTTPError as err:
            status, raw = int(err.code), err.read()
        payload = json.loads(raw.decode("utf-8"))
        assert_contract(method, path, status, payload)
        return status, payload

    def post(self, path: str, body: Any, token: str | None = WORKER_TOKEN) -> tuple[int, Json]:
        data = json.dumps(body).encode("utf-8")
        return self.request("POST", path, data, token, {"Content-Type": "application/json"})

    def system_post(self, path: str, body: Any) -> tuple[int, Json]:
        return self.post(path, body, SYSTEM_TOKEN)

    def get(self, path: str, token: str | None = SYSTEM_TOKEN) -> tuple[int, Json]:
        return self.request("GET", path, None, token)

    def upload(
        self,
        job_id: str,
        metadata: Json,
        data: bytes,
        execution_token: str | None,
        token: str = WORKER_TOKEN,
    ) -> tuple[int, Json]:
        boundary = uuid.uuid4().hex
        body = multipart_body(boundary, metadata, data)
        headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
        if execution_token is not None:
            headers["X-Execution-Token"] = execution_token
        return self.request("POST", f"/jobs/{job_id}/evidence", body, token, headers)


def multipart_body(boundary: str, metadata: Json, data: bytes) -> bytes:
    marker = f"--{boundary}\r\n".encode()
    return b"".join(
        [
            marker,
            b'Content-Disposition: form-data; name="metadata"\r\n',
            b"Content-Type: application/json\r\n\r\n",
            json.dumps(metadata).encode("utf-8"),
            b"\r\n",
            marker,
            b'Content-Disposition: form-data; name="file"; filename="evidence.bin"\r\n',
            b"Content-Type: application/octet-stream\r\n\r\n",
            data,
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
    )
