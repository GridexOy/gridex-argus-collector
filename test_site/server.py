"""Local fixture site server (TZ_SELAIN section 12.2), stdlib only.

Usage: python -m test_site.server [--port 8765] [--host 127.0.0.1]
Serves `test_site/site/` as plain static files. Also importable:
`start(port)` returns a running ThreadingHTTPServer for tests and the panel.
"""

from __future__ import annotations

import argparse
import functools
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SITE_DIR = Path(__file__).resolve().parent / "site"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


class QuietHandler(SimpleHTTPRequestHandler):
    """Static handler without per-request console noise."""

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return


def make_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> ThreadingHTTPServer:
    handler = functools.partial(QuietHandler, directory=str(SITE_DIR))
    return ThreadingHTTPServer((host, port), handler)


def start(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> ThreadingHTTPServer:
    """Start serving in a daemon thread; caller shuts it down with `.shutdown()`."""
    server = make_server(host, port)
    thread = threading.Thread(target=server.serve_forever, name="test-site", daemon=True)
    thread.start()
    return server


def base_url(server: ThreadingHTTPServer) -> str:
    host, port = server.server_address[0], server.server_address[1]
    return f"http://{host!s}:{port}/"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Serve the ARGUS collector fixture site")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)
    server = make_server(args.host, args.port)
    print(f"test site: {base_url(server)} (directory {SITE_DIR})", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
