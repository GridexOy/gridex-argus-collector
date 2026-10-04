"""Reference test stand for ARGUS 2.0's /api/collector (the whole OpenAPI contract).

Stdlib only (`http.server`), never deployed: it stands in for the production
/api/collector until block 6 ships the real one. Every endpoint of
docs/ARGUS20_COLLECTOR_OPENAPI.json is served under /api/collector, plus the
stand-only inspection endpoints under /_stand.

Usage: python -m contract_server.server [--host H] [--port P]
       [--token TOKEN:WORKER_ID]... [--system-token T]... [--state PATH]
       [--lease-seconds N]
Importable: `start(host, port, tokens=..., system_tokens=..., state_path=...,
now=..., lease_seconds=...)` returns a running ContractServer.
"""

from __future__ import annotations

import argparse
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from contract_server.context import DEFAULT_LEASE_SECONDS, Clock, Stand
from contract_server.httpio import make_handler
from contract_server.registry import DEFAULT_SYSTEM_TOKENS, DEFAULT_TOKENS, WorkerRegistry

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8900
HEARTBEAT_PATH = "/api/collector/workers/heartbeat"


class ContractServer(ThreadingHTTPServer):
    """ThreadingHTTPServer carrying the registry and the stand tests can inspect."""

    def __init__(
        self, address: tuple[str, int], handler: type[BaseHTTPRequestHandler], stand: Stand
    ) -> None:
        super().__init__(address, handler)
        self.stand = stand
        self.registry = stand.registry


def make_server(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    tokens: dict[str, str] | None = None,
    *,
    system_tokens: set[str] | frozenset[str] | None = None,
    state_path: Path | None = None,
    now: Clock | None = None,
    lease_seconds: float = DEFAULT_LEASE_SECONDS,
) -> ContractServer:
    registry = WorkerRegistry(
        tokens=dict(DEFAULT_TOKENS if tokens is None else tokens),
        system_tokens=set(DEFAULT_SYSTEM_TOKENS if system_tokens is None else system_tokens),
    )
    stand = Stand.create(registry, state_path, now, lease_seconds)
    return ContractServer((host, port), make_handler(stand), stand)


def start(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    tokens: dict[str, str] | None = None,
    *,
    system_tokens: set[str] | frozenset[str] | None = None,
    state_path: Path | None = None,
    now: Clock | None = None,
    lease_seconds: float = DEFAULT_LEASE_SECONDS,
) -> ContractServer:
    """Start serving in a daemon thread; caller shuts it down with `.shutdown()`."""
    server = make_server(
        host,
        port,
        tokens,
        system_tokens=system_tokens,
        state_path=state_path,
        now=now,
        lease_seconds=lease_seconds,
    )
    thread = threading.Thread(target=server.serve_forever, name="contract-server", daemon=True)
    thread.start()
    return server


def base_url(server: ThreadingHTTPServer) -> str:
    host, port = server.server_address[0], server.server_address[1]
    return f"http://{host!s}:{port}"


def _parse_token_arg(item: str) -> tuple[str, str]:
    token, _, worker_id = item.partition(":")
    return token, worker_id or token


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve the ARGUS /api/collector test stand")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--token",
        action="append",
        dest="tokens",
        metavar="TOKEN:WORKER_ID",
        help="extra worker token, e.g. my-token:worker-x (repeatable)",
    )
    parser.add_argument(
        "--system-token",
        action="append",
        dest="system_tokens",
        metavar="TOKEN",
        help="extra system token (repeatable)",
    )
    parser.add_argument(
        "--state",
        type=Path,
        default=None,
        metavar="PATH",
        help="persist the state as JSON here (evidence in PATH.evidence/)",
    )
    parser.add_argument("--lease-seconds", type=float, default=DEFAULT_LEASE_SECONDS)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    tokens = dict(DEFAULT_TOKENS)
    tokens.update(_parse_token_arg(item) for item in args.tokens or [])
    system_tokens = set(DEFAULT_SYSTEM_TOKENS) | set(args.system_tokens or [])
    server = make_server(
        args.host,
        args.port,
        tokens,
        system_tokens=system_tokens,
        state_path=args.state,
        lease_seconds=args.lease_seconds,
    )
    print(
        f"contract server: {base_url(server)}/api/collector (workers: "
        f"{sorted(set(tokens.values()))}, state: {args.state or 'memory'})",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
