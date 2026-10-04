"""Generated HTTP transport for the api_client module (mechanically generated).

Source: docs/ARGUS20_COLLECTOR_OPENAPI.json.
Do not edit by hand -- see api_client/README.md to regenerate.
stdlib-only `urllib.request`, no third-party dependency. `proxy_mode="system"`
honors the OS proxy configuration (needed for the real ARGUS host,
ARGUS20_TZ_TANDEM.md pair A1 item 4); `proxy_mode="direct"` never uses a
proxy (needed against loopback/contract_server, where the Windows system
proxy answers 127.0.0.1 with a 502 -- see ARGUS20_COLLECTOR_CHANGELOG.md,
commit 6b6467b). The caller decides the mode; this module never inspects
the target host to guess it -- that is config-reading, a different module's job.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Literal

from argus_collector.api_client.serialization import (
    error_from_json,
    heartbeat_request_to_json,
    heartbeat_response_from_json,
)
from argus_collector.api_client.service import (
    Error,
    HeartbeatRequest,
    HeartbeatResponse,
)

SYSTEM_OPENER = urllib.request.build_opener()
DIRECT_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
ProxyMode = Literal["system", "direct"]


class ApiError(RuntimeError):
    """A non-2xx response, or a 2xx one whose body did not parse. `error` is the
    parsed Error body when the server sent one."""

    def __init__(self, status: int, error: Error | None, retry_after: str | None, raw: str) -> None:
        detail = error.detail if error is not None else raw[:300]
        super().__init__(f"HTTP {status}: {detail}")
        self.status = status
        self.error = error
        self.retry_after = retry_after


def _opener(proxy_mode: ProxyMode) -> urllib.request.OpenerDirector:
    return DIRECT_OPENER if proxy_mode == "direct" else SYSTEM_OPENER


def _post(
    base_url: str,
    path: str,
    token: str,
    body: dict[str, Any],
    proxy_mode: ProxyMode,
    timeout_s: float,
) -> tuple[int, bytes]:
    url = base_url.rstrip("/") + path
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
    }
    data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with _opener(proxy_mode).open(request, timeout=timeout_s) as response:
            return int(response.status), bytes(response.read())
    except urllib.error.HTTPError as exc:
        raise _api_error_from_http(exc) from exc
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise ApiError(0, None, None, f"{url}: {exc}") from exc


def _api_error_from_http(exc: urllib.error.HTTPError) -> ApiError:
    raw = exc.read().decode("utf-8", errors="replace")
    retry_after = exc.headers.get("Retry-After") if exc.headers is not None else None
    parsed: Error | None = None
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            parsed = error_from_json(data)
    except (ValueError, KeyError, TypeError):
        parsed = None
    return ApiError(exc.code, parsed, retry_after, raw[:300])


def _parse_json_body(status: int, raw: bytes) -> dict[str, Any]:
    try:
        data = json.loads(raw.decode("utf-8"))
    except ValueError as exc:
        raise ApiError(status, None, None, f"not JSON: {raw[:120]!r}") from exc
    if not isinstance(data, dict):
        raise ApiError(status, None, None, f"not a JSON object: {raw[:120]!r}")
    return data


def heartbeat(
    base_url: str,
    token: str,
    request: HeartbeatRequest,
    *,
    proxy_mode: ProxyMode = "system",
    timeout_s: float = 10.0,
) -> HeartbeatResponse:
    """POST /workers/heartbeat (WorkerBearer)."""
    status, raw = _post(
        base_url,
        '/workers/heartbeat',
        token,
        heartbeat_request_to_json(request),
        proxy_mode,
        timeout_s,
    )
    return heartbeat_response_from_json(_parse_json_body(status, raw))
