"""Reference OpenAPI test double for /api/collector (TZ_TANDEM pair A1).

Stdlib only, following the shape of test_site/server.py (static file server)
and collector/tests/fake_model_server.py (small stdlib JSON API test
double). Implements exactly one endpoint: POST /api/collector/workers/heartbeat.
This is NOT the real ARGUS server -- it stands in for the missing production
/api/collector until the owning team's pair B1 ships the real one; it is
never reachable from prod.

Usage: python -m contract_server.server [--port 8900] [--host 127.0.0.1]
Also importable: `start(host, port, tokens=...)` returns a running
ContractServer (a ThreadingHTTPServer) for tests and the panel's
"Testaa yhteys" smoke check. See README.md for how to seed a test token.
"""

from __future__ import annotations

import argparse
import json
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from contract_server import heartbeat
from contract_server.errors import ApiError
from contract_server.registry import WorkerRegistry

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8900
HEARTBEAT_PATH = "/api/collector/workers/heartbeat"


class ContractServer(ThreadingHTTPServer):
    """ThreadingHTTPServer carrying the worker registry tests can inspect."""

    def __init__(
        self,
        address: tuple[str, int],
        handler: type[BaseHTTPRequestHandler],
        registry: WorkerRegistry,
    ) -> None:
        super().__init__(address, handler)
        self.registry = registry


def _extract_token(handler: BaseHTTPRequestHandler) -> str | None:
    header = handler.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    token = header[len("Bearer "):].strip()
    return token or None


def _read_body(handler: BaseHTTPRequestHandler, request_id: str) -> Any:
    length = int(handler.headers.get("Content-Length", "0"))
    raw = handler.rfile.read(length) if length else b""
    if not raw:
        raise ApiError(400, "invalid_input", "empty request body", request_id=request_id)
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ApiError(
            400, "invalid_input", f"malformed JSON body: {exc}", request_id=request_id
        ) from exc


def _send_json(
    handler: BaseHTTPRequestHandler,
    status: int,
    payload: dict[str, Any],
    retry_after: bool = False,
) -> None:
    raw = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(raw)))
    if retry_after:
        handler.send_header("Retry-After", "1")
    handler.end_headers()
    handler.wfile.write(raw)


def _handle_heartbeat(
    handler: BaseHTTPRequestHandler, registry: WorkerRegistry, request_id: str
) -> None:
    if handler.path != HEARTBEAT_PATH:
        raise ApiError(404, "not_found", "unknown path", request_id=request_id)
    # Always drain the request body first, even for a request we are about to
    # reject: closing the connection with unread bytes still in the socket's
    # receive buffer triggers a TCP RST on Windows (ConnectionAbortedError on
    # the client, sometimes before it even sees the response).
    body = _read_body(handler, request_id)
    worker_id = registry.resolve(_extract_token(handler))
    if worker_id is None:
        raise ApiError(401, "unauthorized", "unknown or missing token", request_id=request_id)
    heartbeat.parse_request(body, request_id)
    registry.record_heartbeat(worker_id, heartbeat.now())
    _send_json(handler, 200, heartbeat.build_response())


def make_handler(registry: WorkerRegistry) -> type[BaseHTTPRequestHandler]:
    """Bind one registry to a fresh Handler type (http.server wants a type)."""

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            return

        def do_POST(self) -> None:  # noqa: N802 - http.server API
            request_id = uuid.uuid4().hex
            try:
                _handle_heartbeat(self, registry, request_id)
            except ApiError as exc:
                _send_json(self, exc.status, exc.body(), retry_after=exc.status == 429)

    return Handler


def make_server(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    tokens: dict[str, str] | None = None,
) -> ContractServer:
    registry = WorkerRegistry() if tokens is None else WorkerRegistry(tokens=dict(tokens))
    return ContractServer((host, port), make_handler(registry), registry)


def start(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    tokens: dict[str, str] | None = None,
) -> ContractServer:
    """Start serving in a daemon thread; caller shuts it down with `.shutdown()`."""
    server = make_server(host, port, tokens)
    thread = threading.Thread(target=server.serve_forever, name="contract-server", daemon=True)
    thread.start()
    return server


def base_url(server: ThreadingHTTPServer) -> str:
    host, port = server.server_address[0], server.server_address[1]
    return f"http://{host!s}:{port}"


def _parse_token_arg(item: str) -> tuple[str, str]:
    token, _, worker_id = item.partition(":")
    return token, worker_id or token


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Serve the ARGUS /api/collector test double")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--token",
        action="append",
        dest="tokens",
        metavar="TOKEN:WORKER_ID",
        help="extra worker token to seed, e.g. my-token:worker-x (repeatable)",
    )
    args = parser.parse_args(argv)
    tokens = dict(WorkerRegistry().tokens)
    tokens.update(_parse_token_arg(item) for item in args.tokens or [])
    server = make_server(args.host, args.port, tokens)
    url = base_url(server) + HEARTBEAT_PATH
    print(f"contract server: {url} (tokens: {sorted(tokens)})", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
