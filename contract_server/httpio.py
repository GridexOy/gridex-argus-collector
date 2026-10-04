"""HTTP plumbing of the stand: draining request bodies, JSON replies, the Handler."""

from __future__ import annotations

import json
import uuid
from http.server import BaseHTTPRequestHandler
from typing import Any

from contract_server import routes
from contract_server.context import Stand
from contract_server.errors import ApiError

MAX_BODY_BYTES = 64 * 1024 * 1024
CHUNK = 1024 * 1024


def read_body(handler: BaseHTTPRequestHandler) -> bytes | None:
    """The request body, always drained; None when it exceeds MAX_BODY_BYTES.

    Closing a connection with unread bytes in the receive buffer triggers a
    TCP RST on Windows (ConnectionAbortedError on the client, sometimes before
    it sees the response), so even a rejected body is read to the end.
    """
    try:
        length = max(int(handler.headers.get("Content-Length", "0")), 0)
    except ValueError:
        length = 0
    if length <= MAX_BODY_BYTES:
        return handler.rfile.read(length) if length else b""
    while length > 0:
        chunk = handler.rfile.read(min(CHUNK, length))
        if not chunk:
            break
        length -= len(chunk)
    return None


def send_json(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    raw = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(raw)))
    if status == 429:
        handler.send_header("Retry-After", "1")
    handler.end_headers()
    handler.wfile.write(raw)


def make_handler(stand: Stand) -> type[BaseHTTPRequestHandler]:
    """Bind one stand to a fresh Handler type (http.server wants a type)."""

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            return

        def _serve(self) -> None:
            request_id = uuid.uuid4().hex
            body = read_body(self)
            if body is None:
                error = ApiError(413, "payload_too_large", "request body too large")
                error.request_id = request_id
                send_json(self, 413, error.body())
                return
            headers = {key.lower(): value for key, value in self.headers.items()}
            status, payload = routes.dispatch(
                stand, self.command, self.path, headers, body, request_id
            )
            send_json(self, status, payload)

        do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = _serve

    return Handler
