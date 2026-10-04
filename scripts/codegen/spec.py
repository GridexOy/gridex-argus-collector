"""Load the OpenAPI document and locate the manifest's operations within it.

Generic on purpose: nothing here names a specific operation or schema. Only
local `#/components/schemas/<Name>` refs are supported, which is everything
this document uses.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

JsonDict = dict[str, Any]
HTTP_METHODS = ("get", "post", "put", "patch", "delete")
SCHEMA_REF_PREFIX = "#/components/schemas/"
JSON_MEDIA = "application/json"
MULTIPART_MEDIA = "multipart/form-data"


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
    """The single (bearer) security scheme name the operation requires."""
    security = operation.get("security") or []
    op_id = operation.get("operationId")
    if len(security) != 1 or len(security[0]) != 1:
        raise SpecError(f"operation {op_id!r} needs exactly one security scheme")
    scheme_name = next(iter(security[0]))
    scheme = spec["components"].get("securitySchemes", {}).get(scheme_name)
    if not isinstance(scheme, dict):
        raise SpecError(f"security scheme {scheme_name!r} is not declared")
    if scheme.get("type") != "http" or scheme.get("scheme") != "bearer":
        raise SpecError(f"security scheme {scheme_name!r} is not an HTTP bearer scheme")
    return scheme_name


def parameters(operation: JsonDict, location: str) -> list[JsonDict]:
    """The operation's parameters in `location` (path/header/query), in document order."""
    found = []
    for param in operation.get("parameters") or []:
        if "$ref" in param:
            raise SpecError(f"{operation.get('operationId')!r}: parameter $ref is not supported")
        if param.get("in") == location:
            found.append(param)
    return found


def request_body(operation: JsonDict) -> tuple[str, JsonDict, JsonDict]:
    """(media type, schema, encoding) of the operation's single request body."""
    body = operation.get("requestBody")
    op_id = operation.get("operationId")
    if not isinstance(body, dict) or not body.get("content"):
        raise SpecError(f"operation {op_id!r} has no requestBody")
    content = body["content"]
    if len(content) != 1:
        raise SpecError(f"operation {op_id!r}: expected exactly one request media type")
    media, entry = next(iter(content.items()))
    if media not in (JSON_MEDIA, MULTIPART_MEDIA):
        raise SpecError(f"operation {op_id!r}: unsupported request media type {media!r}")
    return media, entry["schema"], entry.get("encoding") or {}


def success_schema_ref(operation: JsonDict) -> str:
    """The $ref every 2xx response uses (200 and 201 must agree)."""
    refs = set()
    for status, response in operation["responses"].items():
        if str(status).startswith("2"):
            refs.add(_json_schema_ref(operation, response))
    if len(refs) != 1:
        raise SpecError(f"{operation.get('operationId')!r}: 2xx responses must share one schema")
    return refs.pop()


def error_schema_ref(operation: JsonDict) -> str:
    return _json_schema_ref(operation, operation["responses"]["default"])


def _json_schema_ref(operation: JsonDict, response: JsonDict) -> str:
    schema = (response.get("content") or {}).get(JSON_MEDIA, {}).get("schema", {})
    if "$ref" not in schema:
        raise SpecError(f"{operation.get('operationId')!r}: response needs a JSON schema $ref")
    return str(schema["$ref"])
