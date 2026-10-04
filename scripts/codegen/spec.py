"""Load the OpenAPI document and locate the manifest's operations within it.

Generic on purpose: nothing here is specific to `heartbeat`. Only local
`#/components/schemas/<Name>` refs are supported, which is everything this
document uses.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

JsonDict = dict[str, Any]
HTTP_METHODS = ("get", "post", "put", "patch", "delete")
SCHEMA_REF_PREFIX = "#/components/schemas/"


class SpecError(RuntimeError):
    """The OpenAPI document does not match what the generator expects."""


def load_spec(path: Path) -> JsonDict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "paths" not in data or "components" not in data:
        raise SpecError(f"{path}: not an OpenAPI document")
    return data


def find_operation(spec: JsonDict, operation_id: str) -> tuple[str, str, JsonDict]:
    """Return (path, method, operation object) for operationId, in document order."""
    for path, methods in spec["paths"].items():
        if not isinstance(methods, dict):
            continue
        for method in HTTP_METHODS:
            operation = methods.get(method)
            if isinstance(operation, dict) and operation.get("operationId") == operation_id:
                return path, method, operation
    raise SpecError(f"operationId {operation_id!r} not found in the OpenAPI document")


def resolve_ref(spec: JsonDict, ref: str) -> tuple[str, JsonDict]:
    """Resolve a local schema $ref; return (schema name, schema object)."""
    if not ref.startswith(SCHEMA_REF_PREFIX):
        raise SpecError(f"unsupported $ref: {ref!r} (only local component schemas are supported)")
    name = ref[len(SCHEMA_REF_PREFIX) :]
    schemas = spec["components"]["schemas"]
    if name not in schemas:
        raise SpecError(f"$ref {ref!r} has no matching schema")
    return name, schemas[name]


def security_scheme(spec: JsonDict, operation: JsonDict) -> str:
    """The single security scheme name the operation requires."""
    security = operation.get("security") or []
    op_id = operation.get("operationId")
    if len(security) != 1 or len(security[0]) != 1:
        raise SpecError(f"operation {op_id!r} needs exactly one security scheme")
    scheme_name = next(iter(security[0]))
    if scheme_name not in spec["components"].get("securitySchemes", {}):
        raise SpecError(f"security scheme {scheme_name!r} is not declared")
    return scheme_name


def body_schema_name(spec: JsonDict, operation: JsonDict) -> str:
    body = operation.get("requestBody")
    if not isinstance(body, dict):
        raise SpecError(f"operation {operation.get('operationId')!r} has no requestBody")
    schema = body["content"]["application/json"]["schema"]
    name, _ = resolve_ref(spec, schema["$ref"])
    return name


def response_schema_name(spec: JsonDict, operation: JsonDict, status: str) -> str:
    response = operation["responses"][status]
    schema = response["content"]["application/json"]["schema"]
    name, _ = resolve_ref(spec, schema["$ref"])
    return name
