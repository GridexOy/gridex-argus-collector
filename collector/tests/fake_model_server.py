"""Test double of an OpenAI-compatible local endpoint (tests only, never in the UI).

`FakeModelServer(policy)` serves `GET /v1/models` and `POST /v1/chat/completions`
on 127.0.0.1; `policy(system, user) -> str` decides the reply content. Every
request body is kept in `requests` so tests can inspect prompts.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

Policy = Callable[[str, str], str]
MODEL_ID = "fake-instruct"


class FakeModelServer:
    def __init__(self, policy: Policy, model_id: str = MODEL_ID) -> None:
        self.policy = policy
        self.model_id = model_id
        self.requests: list[dict[str, Any]] = []
        self.fail_next = 0
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler_class())
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def endpoint(self) -> str:
        return f"http://127.0.0.1:{self._server.server_address[1]}/v1"

    def start(self) -> FakeModelServer:
        self._thread.start()
        return self

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()

    def _handler_class(self) -> type[BaseHTTPRequestHandler]:
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:  # noqa: A002
                return

            def _send(self, code: int, payload: dict[str, Any]) -> None:
                raw = json.dumps(payload).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_GET(self) -> None:  # noqa: N802 - http.server API
                if self.path.rstrip("/").endswith("/models"):
                    self._send(200, {"object": "list", "data": [{"id": owner.model_id}]})
                else:
                    self._send(404, {"error": "not found"})

            def do_POST(self) -> None:  # noqa: N802 - http.server API
                length = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(length).decode("utf-8"))
                owner.requests.append(body)
                if owner.fail_next > 0:
                    owner.fail_next -= 1
                    self._send(500, {"error": "simulated failure"})
                    return
                messages = body.get("messages", [])
                system = next((m["content"] for m in messages if m["role"] == "system"), "")
                user = next((m["content"] for m in messages if m["role"] == "user"), "")
                content = owner.policy(system, user)
                self._send(200, completion(owner.model_id, content, len(user) // 4))

        return Handler


def completion(model_id: str, content: str, prompt_tokens: int) -> dict[str, Any]:
    return {
        "id": "chatcmpl-fake",
        "object": "chat.completion",
        "model": model_id,
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": content},
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": len(content) // 4,
            "total_tokens": prompt_tokens + len(content) // 4,
        },
    }
