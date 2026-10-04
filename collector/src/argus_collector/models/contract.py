"""Single entry point of the `models` module: the local model adapter (M2).

Talks to an OpenAI-compatible chat endpoint on this PC (Ollama
`http://127.0.0.1:11434/v1` by default, llama.cpp server works the same).
The system proxy is never used for it (urllib `ProxyHandler({})`): the
Windows proxy on MAIN-PC answers 127.0.0.1 with 502. Every call is logged
to the `model_calls` table with tokens, milliseconds and `cost_eur = 0`
(TZ_SELAIN section 3.2 p.5). The model never searches and never invents:
callers verify every value it returns against the page text.
"""

from __future__ import annotations

import sqlite3
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from argus_collector.models import repository, service
from argus_collector.models.repository import ModelError
from argus_collector.models.service import CallRecord, Health, ModelConfig, ModelReply

__all__ = [
    "DEFAULT_ENDPOINT",
    "DEFAULT_MODEL",
    "CallRecord",
    "CallListener",
    "Health",
    "ModelClient",
    "ModelConfig",
    "ModelError",
    "ModelReply",
    "health",
    "resolve_config",
]

CallListener = Callable[[CallRecord], None]
DEFAULT_ENDPOINT = service.DEFAULT_ENDPOINT
DEFAULT_MODEL = service.DEFAULT_MODEL
PROVIDER = "local"


def resolve_config(endpoint: str = "", name: str = "") -> ModelConfig:
    """ModelConfig from `config.yaml` values; empty strings take the defaults."""
    return ModelConfig(endpoint=endpoint or DEFAULT_ENDPOINT, name=name or DEFAULT_MODEL)


def health(endpoint: str, name: str, timeout_s: float = service.HEALTH_TIMEOUT_S) -> Health:
    """GET <endpoint>/models without proxy; `model_listed` when `name` is served."""
    try:
        listed = repository.list_models(endpoint, timeout_s)
    except ModelError as exc:
        return Health(reachable=False, model_listed=False, detail=f"no answer: {exc}")
    return service.health_from_models(listed, name)


class ModelClient:
    """Chat completions in JSON mode against the configured local endpoint."""

    def __init__(
        self,
        config: ModelConfig,
        conn: sqlite3.Connection | None = None,
        listener: CallListener | None = None,
    ) -> None:
        self.config = config
        self.conn = conn
        self.listener = listener

    def chat(self, system: str, user: str, purpose: str) -> ModelReply:
        """One chat completion (plain text). Raises ModelError; the call is logged either way."""
        body = service.request_body(self.config, system, user, json_mode=False)
        return self._send(body, purpose)

    def chat_json(self, system: str, user: str, purpose: str) -> dict[str, Any]:
        """One chat completion in JSON mode, parsed to a dict (one retry on bad JSON)."""
        body = service.request_body(self.config, system, user, json_mode=True)
        reply = self._send(body, purpose)
        parsed = service.parse_json_reply(reply.content)
        if parsed is None:
            reply = self._send(body, purpose + ":retry")
            parsed = service.parse_json_reply(reply.content)
        if parsed is None:
            raise ModelError(f"model {self.config.name} did not return a JSON object")
        return parsed

    def _send(self, body: dict[str, Any], purpose: str) -> ModelReply:
        started_at = datetime.now(UTC).isoformat(timespec="milliseconds")
        started = time.monotonic()
        try:
            reply = repository.post_chat(self.config, body)
        except ModelError as exc:
            if self.conn is not None:
                repository.log_call(self.conn, self.config, purpose, None, str(exc))
            elapsed = int((time.monotonic() - started) * 1000)
            self._notify(CallRecord(purpose, self.config.name, started_at, elapsed, 0, 0, False,
                                    str(exc)))
            raise
        if self.conn is not None:
            repository.log_call(self.conn, self.config, purpose, reply, "")
        self._notify(
            CallRecord(purpose, reply.model or self.config.name, started_at, reply.elapsed_ms,
                       reply.prompt_tokens, reply.completion_tokens, True)
        )
        return reply

    def _notify(self, record: CallRecord) -> None:
        if self.listener is not None:
            self.listener(record)
