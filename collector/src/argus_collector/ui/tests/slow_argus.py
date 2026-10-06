"""Test stand: forwards to contract_server; heartbeats can be made slow (no answer in time)."""

from __future__ import annotations

import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# never the Windows system proxy: MAIN-PC has one, and loopback must stay local
DIRECT = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class SlowArgus:
    def __init__(self, upstream: str) -> None:
        self.upstream, self.delay_s, self.heartbeats = upstream, 0.0, 0
        stand = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802 - http.server API
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length)
                if self.path.endswith("/workers/heartbeat"):
                    stand.heartbeats += 1
                    time.sleep(stand.delay_s)
                req = urllib.request.Request(stand.upstream + self.path, data=body, method="POST")
                for key in ("Authorization", "Content-Type", "Accept"):
                    if self.headers.get(key):
                        req.add_header(key, self.headers[key])
                try:
                    with DIRECT.open(req, timeout=10) as resp:
                        status, data = resp.status, resp.read()
                except urllib.error.HTTPError as exc:
                    status, data = exc.code, exc.read()
                try:
                    self.send_response(status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                except OSError:
                    pass  # the client gave up waiting (the slow case)

            def log_message(self, *args: object) -> None:
                return None

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def address(self) -> str:
        return f"http://127.0.0.1:{self.server.server_address[1]}"

    def start(self) -> SlowArgus:
        self.thread.start()
        return self

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()
