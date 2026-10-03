"""I/O of the model adapter: HTTP to the local endpoint, `model_calls` rows.

The opener has an empty ProxyHandler: the local model is never reached
through the system proxy (Windows registry proxy answers 127.0.0.1 with 502).
"""

from __future__ import annotations

import json
import sqlite3
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any

from argus_collector.models.service import ModelConfig, ModelReply, parse_models, parse_reply

PROVIDER = "local"
COST_EUR = 0.0
DIRECT_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}


class ModelError(RuntimeError):
    """The endpoint did not answer, answered with an error or with a bad document."""


def _request(url: str, body: dict[str, Any] | None, timeout_s: float) -> Any:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers=HEADERS, method="POST" if data else "GET")
    try:
        with DIRECT_OPENER.open(req, timeout=timeout_s) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise ModelError(f"HTTP {exc.code} from {url}: {detail}") from exc
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise ModelError(f"{url}: {exc}") from exc
    try:
        return json.loads(raw.decode("utf-8"))
    except ValueError as exc:
        raise ModelError(f"{url}: not JSON: {raw[:120]!r}") from exc


def list_models(endpoint: str, timeout_s: float) -> list[str]:
    data = _request(endpoint.rstrip("/") + "/models", None, timeout_s)
    try:
        return parse_models(data)
    except ValueError as exc:
        raise ModelError(str(exc)) from exc


def post_chat(config: ModelConfig, body: dict[str, Any]) -> ModelReply:
    started = time.monotonic()
    data = _request(config.endpoint.rstrip("/") + "/chat/completions", body, config.timeout_s)
    elapsed_ms = int((time.monotonic() - started) * 1000)
    try:
        return parse_reply(data, elapsed_ms)
    except ValueError as exc:
        raise ModelError(str(exc)) from exc


def log_call(
    conn: sqlite3.Connection,
    config: ModelConfig,
    purpose: str,
    reply: ModelReply | None,
    error: str,
) -> None:
    with conn:
        conn.execute(
            "INSERT INTO model_calls (called_at, provider, model, purpose, prompt_tokens,"
            " completion_tokens, elapsed_ms, cost_eur, ok, error)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                datetime.now(UTC).isoformat(timespec="seconds"),
                PROVIDER,
                config.name,
                purpose,
                reply.prompt_tokens if reply else 0,
                reply.completion_tokens if reply else 0,
                reply.elapsed_ms if reply else 0,
                COST_EUR,
                1 if reply else 0,
                error,
            ),
        )


def call_totals(conn: sqlite3.Connection) -> dict[str, int]:
    row = conn.execute(
        "SELECT COUNT(*), COALESCE(SUM(prompt_tokens), 0), COALESCE(SUM(completion_tokens), 0),"
        " COALESCE(SUM(elapsed_ms), 0) FROM model_calls"
    ).fetchone()
    return {
        "calls": int(row[0]),
        "prompt_tokens": int(row[1]),
        "completion_tokens": int(row[2]),
        "elapsed_ms": int(row[3]),
    }
