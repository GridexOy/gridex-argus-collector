"""Minimal stdlib double of the ARGUS collector API (test-only).

Records every request (path, lower-cased headers, raw body) and answers with
the queued replies in order; mirrors the shape of fake_model_server.py.
"""

from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

NO_REPLY = {"code": "no_reply_queued", "detail": "test bug", "retryable": False, "request_id": "t"}
PART_NAME = re.compile(r'name="([^"]*)"')


@dataclass(frozen=True)
class Received:
    path: str
    headers: dict[str, str]
    body: bytes

    def json(self) -> Any:
        return json.loads(self.body.decode("utf-8"))


class FakeArgus:
    def __init__(self) -> None:
        self.requests: list[Received] = []
        self._replies: list[tuple[int, Any, dict[str, str]]] = []
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler_class())
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    @property
    def last(self) -> Received:
        return self.requests[-1]

    def start(self) -> FakeArgus:
        self._thread.start()
        return self

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()

    def reply(self, status: int, payload: Any, headers: dict[str, str] | None = None) -> None:
        self._replies.append((status, payload, headers or {}))

    def _answer(self, handler: BaseHTTPRequestHandler) -> None:
        length = int(handler.headers.get("Content-Length", "0"))
        headers = {key.lower(): value for key, value in handler.headers.items()}
        self.requests.append(Received(handler.path, headers, handler.rfile.read(length)))
        status, payload, extra = self._replies.pop(0) if self._replies else (500, NO_REPLY, {})
        raw = json.dumps(payload).encode("utf-8")
        handler.send_response(status)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(raw)))
        for key, value in extra.items():
            handler.send_header(key, value)
        handler.end_headers()
        handler.wfile.write(raw)

    def _handler_class(self) -> type[BaseHTTPRequestHandler]:
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:  # noqa: A002
                return

            def do_POST(self) -> None:  # noqa: N802 - http.server API
                owner._answer(self)

        return Handler


def parse_multipart(content_type: str, body: bytes) -> dict[str, tuple[dict[str, str], bytes]]:
    """Strict multipart/form-data parser: {part name: (lower-cased headers, content)}."""
    media, _, boundary = content_type.partition("; boundary=")
    assert media == "multipart/form-data" and boundary
    delimiter = b"--" + boundary.encode("ascii")
    assert body.startswith(delimiter + b"\r\n") and body.endswith(delimiter + b"--\r\n")
    parts: dict[str, tuple[dict[str, str], bytes]] = {}
    for section in body[: -len(delimiter + b"--\r\n")].split(delimiter)[1:]:
        assert section.startswith(b"\r\n") and section.endswith(b"\r\n")
        head, separator, content = section[2:-2].partition(b"\r\n\r\n")
        assert separator, "a part needs a blank line between headers and content"
        lines = head.decode("utf-8").split("\r\n")
        headers = {k.lower(): v for k, _, v in (line.partition(": ") for line in lines)}
        match = PART_NAME.search(headers["content-disposition"])
        assert match is not None
        parts[match.group(1)] = (headers, content)
    return parts
