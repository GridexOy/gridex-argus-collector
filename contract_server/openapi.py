"""The OpenAPI document as the single source of every schema the stand checks.

`docs/ARGUS20_COLLECTOR_OPENAPI.json` is read once at import. `check()`
validates against a component by name (or any schema dict); the operation
helpers give the request/response schema of an operationId, which the tests
use to validate every response body.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from contract_server.schema import Schema, validate

DOC_PATH = Path(__file__).resolve().parents[1] / "docs" / "ARGUS20_COLLECTOR_OPENAPI.json"
DOC: dict[str, Any] = json.loads(DOC_PATH.read_text(encoding="utf-8"))
BASE_PATH = "/api/collector"
REF_PREFIX = "#/components/schemas/"
SCHEMAS: dict[str, Schema] = DOC["components"]["schemas"]


def resolve(ref: str) -> Schema:
    if not ref.startswith(REF_PREFIX) or ref[len(REF_PREFIX) :] not in SCHEMAS:
        raise KeyError(f"unresolvable $ref {ref!r}")
    return SCHEMAS[ref[len(REF_PREFIX) :]]


def ref(name: str) -> Schema:
    return {"$ref": REF_PREFIX + name}


def check(instance: Any, schema: str | Schema) -> list[str]:
    """Violations of a component (by name) or of an inline schema."""
    target = ref(schema) if isinstance(schema, str) else schema
    return validate(instance, target, resolve)


def operation(operation_id: str) -> tuple[str, str, dict[str, Any]]:
    """(path template, method, operation object) of an operationId."""
    for template, methods in DOC["paths"].items():
        for method, op in methods.items():
            if op.get("operationId") == operation_id:
                return template, method.upper(), op
    raise KeyError(operation_id)


def operation_for(method: str, path: str) -> str | None:
    """operationId serving `method path` (a full /api/collector/... path), or None."""
    if not path.startswith(BASE_PATH + "/"):
        return None
    rest = path[len(BASE_PATH) :]
    for template, methods in DOC["paths"].items():
        pattern = "^" + re.sub(r"\{\w+\}", "[^/]+", template) + "$"
        op = methods.get(method.lower())
        if op is not None and re.match(pattern, rest):
            return str(op["operationId"])
    return None


def response_schema(operation_id: str, status: int) -> Schema:
    """Schema of the response body: the status entry when present, else `default`."""
    responses = operation(operation_id)[2]["responses"]
    entry = responses.get(str(status)) or responses["default"]
    return dict(entry["content"]["application/json"]["schema"])


def request_schema(operation_id: str) -> Schema:
    content = operation(operation_id)[2]["requestBody"]["content"]
    media = content.get("application/json") or content["multipart/form-data"]
    return dict(media["schema"])
