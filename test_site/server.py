"""Local fixture site server (TZ_SELAIN section 12.2), stdlib only.

Usage: python -m test_site.server [--port 8765] [--host 127.0.0.1]
`http://127.0.0.1:<port>/` serves `test_site/site/` (company `fixture_oy`).
Every other fixture company is a virtual host `<label>.localhost:<port>`
served from `test_site/sites/<label>/` (Chrome resolves `*.localhost` to the
loopback address itself, so no hosts file is needed). `REDIRECTS` sends a
label to another host on the same port (a seed that leaves its approved
host). Also importable: `start(port)` returns a running ThreadingHTTPServer.
"""

from __future__ import annotations

import argparse
import functools
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SITE_DIR = Path(__file__).resolve().parent / "site"
SITES_DIR = Path(__file__).resolve().parent / "sites"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
VHOST_SUFFIX = ".localhost"
# label -> label: `katsa-oy` is the seed of company katsa; it redirects to a
# host that is not in its approved_hosts (K7, TZ_SELAIN section 12.2).
REDIRECTS = {"katsa-oy": "katsa-group"}


def split_host(header: str) -> tuple[str, str]:
    """`Host` header -> (host name lower-cased, port text or "")."""
    host, _, port = header.strip().lower().rpartition(":")
    if not host or not port.isdigit():
        return header.strip().lower(), ""
    return host, port


def vhost_label(host: str) -> str | None:
    if host.endswith(VHOST_SUFFIX) and len(host) > len(VHOST_SUFFIX):
        return host[: -len(VHOST_SUFFIX)]
    return None


def site_dir_for(host: str) -> Path | None:
    """Directory serving `host`; None for an unknown virtual host."""
    label = vhost_label(host)
    if label is None:
        return SITE_DIR
    folder = SITES_DIR / label
    return folder if folder.is_dir() else None


class SiteHandler(SimpleHTTPRequestHandler):
    """Static handler routed by the Host header, without console noise."""

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return

    def _route(self) -> bool:
        host, port = split_host(self.headers.get("Host", ""))
        label = vhost_label(host)
        if label in REDIRECTS:
            target = f"{REDIRECTS[label]}{VHOST_SUFFIX}" + (f":{port}" if port else "")
            self.send_response(302)
            self.send_header("Location", f"http://{target}{self.path}")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return False
        folder = site_dir_for(host)
        if folder is None:
            self.send_error(404, "unknown fixture host")
            return False
        self.directory = str(folder)
        return True

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        if self._route():
            super().do_GET()

    def do_HEAD(self) -> None:  # noqa: N802 - http.server API
        if self._route():
            super().do_HEAD()


def make_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> ThreadingHTTPServer:
    handler = functools.partial(SiteHandler, directory=str(SITE_DIR))
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


def vhost_url(server: ThreadingHTTPServer, label: str) -> str:
    """Root URL of the virtual host `<label>.localhost` on the server's port."""
    return f"http://{label}{VHOST_SUFFIX}:{server.server_address[1]}/"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Serve the ARGUS collector fixture site")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)
    server = make_server(args.host, args.port)
    print(f"test site: {base_url(server)} (directory {SITE_DIR})", flush=True)
    print(f"virtual hosts: http://<label>.localhost:{args.port}/ from {SITES_DIR}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
