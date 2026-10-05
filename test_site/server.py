"""Local fixture site server (TZ_SELAIN section 12.2), stdlib only.

Usage: python -m test_site.server [--port 8765] [--host 127.0.0.1] [--variant NAME]
`http://127.0.0.1:<port>/` serves `test_site/site/` (company `fixture_oy`).
Every other fixture company is a virtual host `<label>.localhost:<port>`
served from `test_site/sites/<label>/` (Chrome resolves `*.localhost` to the
loopback address itself, so no hosts file is needed). `REDIRECTS` sends a
label to another host on the same port (a seed that leaves its approved
host). Port placeholder, variants and the bot check live in `pages`.
Directories are never listed (a real site has no index pages of folders).
Also importable: `start(port=..., variant=...)` returns a running server.
"""

from __future__ import annotations

import argparse
import functools
import io
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from os import PathLike
from pathlib import Path
from typing import Any, BinaryIO
from urllib.parse import urlsplit

from test_site import pages

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

    def __init__(self, *args: Any, variant: str | None = None, **kwargs: Any) -> None:
        self.variant = variant
        self.port_text = ""
        self.challenge: bytes | None = None
        super().__init__(*args, **kwargs)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return

    def _route(self) -> bool:
        host, port = split_host(self.headers.get("Host", ""))
        self.port_text = port or str(self.connection.getsockname()[1])
        self.challenge = None
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
        cookie = self.headers.get("Cookie", "")
        if pages.needs_challenge(label, urlsplit(self.path).path, cookie, self.variant):
            self.challenge = pages.challenge_page(host, self.variant)
        self.directory = str(folder)
        self._apply_overlay(label)
        return True

    def _apply_overlay(self, label: str | None) -> None:
        overlay = pages.overlay_root(self.variant, label)
        if overlay is None:
            return
        base, self.directory = self.directory, str(overlay)
        if not pages.overlay_serves(Path(self.translate_path(self.path))):
            self.directory = base

    def _html_file(self) -> Path | None:
        """The `.html` file this request names, None for anything else."""
        raw = self.translate_path(self.path)
        path = Path(raw)
        if path.is_dir():
            if not raw.endswith("/"):
                return None  # the base class answers with the redirect to "dir/"
            path = path / "index.html"
        elif raw.endswith("/"):
            return None
        return path if path.suffix == ".html" and path.is_file() else None

    def _send_html(self, body: bytes) -> io.BytesIO:
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        return io.BytesIO(body)

    def send_head(self) -> io.BytesIO | BinaryIO | None:
        if self.challenge is not None:
            return self._send_html(self.challenge)
        page = self._html_file()
        if page is None:
            return super().send_head()
        return self._send_html(pages.substitute_port(page.read_bytes(), self.port_text))

    def list_directory(self, path: str | PathLike[str]) -> io.BytesIO | None:
        self.send_error(404, "File not found")
        return None

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        if self._route():
            super().do_GET()

    def do_HEAD(self) -> None:  # noqa: N802 - http.server API
        if self._route():
            super().do_HEAD()


def make_server(
    host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, variant: str | None = None
) -> ThreadingHTTPServer:
    """Bound server; ValueError for a variant `pages.known_variants()` lacks."""
    chosen = pages.check_variant(variant)
    handler = functools.partial(SiteHandler, directory=str(SITE_DIR), variant=chosen)
    return ThreadingHTTPServer((host, port), handler)


def start(
    host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, variant: str | None = None
) -> ThreadingHTTPServer:
    """Start serving in a daemon thread; caller shuts it down with `.shutdown()`."""
    server = make_server(host, port, variant)
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
    parser.add_argument("--variant", choices=pages.known_variants(), default=None)
    args = parser.parse_args(argv)
    server = make_server(args.host, args.port, args.variant)
    print(f"test site: {base_url(server)} (directory {SITE_DIR})", flush=True)
    print(f"virtual hosts: http://<label>.localhost:{args.port}/ from {SITES_DIR}", flush=True)
    print(f"variant: {args.variant or 'none'}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
