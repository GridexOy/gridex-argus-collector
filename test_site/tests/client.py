"""Test helpers: a running fixture server, requests with an explicit Host header."""

from __future__ import annotations

import http.client
import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

from test_site import server

GOLD_DIR = Path(__file__).resolve().parents[1] / "gold"
WAF_PASS = "fixture_waf=passed"
CHALLENGE_TITLE = "<title>Just a moment...</title>"


@dataclass(frozen=True)
class Reply:
    status: int
    headers: dict[str, str]
    body: bytes

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")


@contextmanager
def running(variant: str | None = None) -> Iterator[ThreadingHTTPServer]:
    srv = server.start(port=0, variant=variant)
    try:
        yield srv
    finally:
        srv.shutdown()
        srv.server_close()


def port_of(srv: ThreadingHTTPServer) -> int:
    return int(srv.server_address[1])


def request(
    srv: ThreadingHTTPServer,
    host: str,
    path: str,
    cookie: str = "",
    method: str = "GET",
    host_port: str | None = None,
) -> Reply:
    """`host_port` None: the server's port in the Host header; "" sends no port."""
    port = port_of(srv)
    shown = str(port) if host_port is None else host_port
    headers = {"Host": f"{host}:{shown}" if shown else host}
    if cookie:
        headers["Cookie"] = cookie
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request(method, path, headers=headers)
        resp = conn.getresponse()
        found = {name.lower(): value for name, value in resp.getheaders()}
        return Reply(resp.status, found, resp.read())
    finally:
        conn.close()


def page(srv: ThreadingHTTPServer, host: str, path: str, cookie: str = "") -> str:
    """Body of a page that must answer 200."""
    reply = request(srv, host, path, cookie)
    assert reply.status == 200, (host, path, reply.status)
    return reply.text


def gold(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((GOLD_DIR / f"{name}.json").read_text(encoding="utf-8"))
    return data
