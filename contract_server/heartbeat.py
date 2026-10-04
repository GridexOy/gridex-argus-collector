"""HeartbeatRequest validation and HeartbeatResponse building (OpenAPI pair A1).

Wire schema 1.1 (`docs/ARGUS20_COLLECTOR_OPENAPI.json`). Only the fields this
test double needs to check are validated; everything else in the request is
accepted as-is since there are no jobs or leases yet in A1.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from contract_server.errors import ApiError

SUPPORTED_SCHEMA_VERSIONS = {"1.1"}
REQUIRED_FIELDS = (
    "worker_id",
    "worker_version",
    "schema_versions",
    "capabilities",
    "collecting",
    "active_jobs",
    "outbox_pending",
    "free_job_slots",
    "browser_available",
    "model_available",
    "acknowledgements",
)


def now() -> datetime:
    return datetime.now(UTC)


def parse_request(body: Any, request_id: str) -> dict[str, Any]:
    """Validate the HeartbeatRequest shape; raise ApiError on the first mismatch."""
    if not isinstance(body, dict):
        raise ApiError(400, "invalid_input", "body must be a JSON object", request_id=request_id)
    missing = [name for name in REQUIRED_FIELDS if name not in body]
    if missing:
        raise ApiError(
            400, "invalid_input", f"missing fields: {', '.join(missing)}", request_id=request_id
        )
    versions = body["schema_versions"]
    if not isinstance(versions, list) or not SUPPORTED_SCHEMA_VERSIONS.intersection(versions):
        raise ApiError(
            400,
            "schema_unsupported",
            f"server supports {sorted(SUPPORTED_SCHEMA_VERSIONS)}",
            request_id=request_id,
        )
    return body


def build_response() -> dict[str, Any]:
    """No jobs exist yet in A1: always an empty lease/command list."""
    return {
        "server_time": now().isoformat(timespec="seconds"),
        "leases": [],
        "commands": [],
    }
