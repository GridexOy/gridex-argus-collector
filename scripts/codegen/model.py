"""Build a ClientModel (enums, dataclasses, operations) reachable from the manifest.

Walks $ref generically from each manifest operation's request/response/error
schema, so adding an operationId to manifest.MANIFEST and rerunning the
generator is enough to cover it later -- nothing here hardcodes a schema
name. The only schema shapes supported are the ones this document actually
uses: plain objects (`additionalProperties: false`), inline string enums,
arrays of those, and the two-element `["<type>", "null"]` nullable form.
"""

from __future__ import annotations

from collections.abc import Sequence

from codegen.naming import enum_member_name, pascal_case
from codegen.spec import (
    JsonDict,
    SpecError,
    body_schema_name,
    find_operation,
    resolve_ref,
    response_schema_name,
    security_scheme,
)
from codegen.types import (
    SCALAR_JSON_TO_PY,
    ClientModel,
    Enqueue,
    EnumSpec,
    FieldSpec,
    ObjectSpec,
    OperationSpec,
)


def build_model(spec: JsonDict, manifest: Sequence[str]) -> ClientModel:
    schemas: dict[str, JsonDict] = {}
    queue: list[str] = []

    def enqueue(name: str) -> None:
        if name in schemas:
            return
        _, schema = resolve_ref(spec, f"#/components/schemas/{name}")
        schemas[name] = schema
        queue.append(name)

    operations = [_operation_spec(spec, operation_id, enqueue) for operation_id in manifest]
    enums: dict[str, EnumSpec] = {}
    object_order: list[str] = []
    object_specs: dict[str, ObjectSpec] = {}
    while queue:
        name = queue.pop(0)
        fields = _fields_for_object(spec, name, schemas[name], enqueue, enums)
        object_order.append(name)
        object_specs[name] = ObjectSpec(name=name, fields=tuple(fields))
    return ClientModel(
        enums=tuple(enums.values()),
        objects=tuple(object_specs[name] for name in object_order),
        operations=tuple(operations),
    )


def _operation_spec(spec: JsonDict, operation_id: str, enqueue: Enqueue) -> OperationSpec:
    path, method, operation = find_operation(spec, operation_id)
    request_name = body_schema_name(spec, operation)
    response_name = response_schema_name(spec, operation, "200")
    error_name = response_schema_name(spec, operation, "default")
    for name in (request_name, response_name, error_name):
        enqueue(name)
    return OperationSpec(
        operation_id=operation_id,
        path=path,
        method=method,
        security_scheme=security_scheme(spec, operation),
        request_schema=request_name,
        response_schema=response_name,
        error_schema=error_name,
    )


def _fields_for_object(
    spec: JsonDict, schema_name: str, schema: JsonDict, enqueue: Enqueue, enums: dict[str, EnumSpec]
) -> list[FieldSpec]:
    if schema.get("type") != "object" or schema.get("additionalProperties") is not False:
        raise SpecError(f"{schema_name}: expected an object with additionalProperties: false")
    required = set(schema.get("required") or [])
    fields = [
        _field_spec(spec, schema_name, name, prop, name in required, enums, enqueue)
        for name, prop in (schema.get("properties") or {}).items()
    ]
    return [f for f in fields if f.required] + [f for f in fields if not f.required]


def _field_spec(
    spec: JsonDict,
    schema_name: str,
    prop_name: str,
    prop_schema: JsonDict,
    required: bool,
    enums: dict[str, EnumSpec],
    enqueue: Enqueue,
) -> FieldSpec:
    if "$ref" in prop_schema:
        ref_name, _ = resolve_ref(spec, prop_schema["$ref"])
        enqueue(ref_name)
        default = _default("object", required, prop_schema)
        return FieldSpec(prop_name, required, "object", ref_name, None, default)
    if prop_schema.get("type") == "array":
        return _array_field(spec, prop_name, prop_schema, required, enqueue)
    if "enum" in prop_schema:
        enum_name = f"{schema_name}{pascal_case(prop_name)}"
        enums.setdefault(enum_name, EnumSpec(enum_name, tuple(prop_schema["enum"])))
        default = _default("enum", required, prop_schema, enum_name)
        return FieldSpec(prop_name, required, "enum", enum_name, None, default)
    prop_type = prop_schema.get("type")
    if isinstance(prop_type, list):
        return _nullable_scalar_field(prop_name, prop_type, required)
    scalar = _scalar(prop_type)
    default = _default(scalar, required, prop_schema)
    return FieldSpec(prop_name, required, scalar, None, None, default)


def _array_field(
    spec: JsonDict, prop_name: str, prop_schema: JsonDict, required: bool, enqueue: Enqueue
) -> FieldSpec:
    items = prop_schema["items"]
    if "$ref" in items:
        ref_name, _ = resolve_ref(spec, items["$ref"])
        enqueue(ref_name)
        default = _default("list_object", required, {})
        return FieldSpec(prop_name, required, "list_object", ref_name, None, default)
    scalar = _scalar(items["type"])
    default = _default("list_scalar", required, {})
    return FieldSpec(prop_name, required, "list_scalar", None, scalar, default)


def _nullable_scalar_field(prop_name: str, prop_type: list[str], required: bool) -> FieldSpec:
    non_null = [t for t in prop_type if t != "null"]
    if len(non_null) != 1 or "null" not in prop_type:
        raise SpecError(f"{prop_name}: unsupported nullable type {prop_type}")
    scalar = _scalar(non_null[0])
    return FieldSpec(prop_name, required, f"{scalar}_or_null", None, None, None)


def _scalar(json_type: object) -> str:
    if not isinstance(json_type, str) or json_type not in SCALAR_JSON_TO_PY:
        raise SpecError(f"unsupported JSON Schema type {json_type!r}")
    return SCALAR_JSON_TO_PY[json_type]


def _default(
    kind: str, required: bool, prop_schema: JsonDict, enum_name: str | None = None
) -> str | None:
    if required:
        return None
    if "default" not in prop_schema:
        return "None"
    value = prop_schema["default"]
    if kind == "enum":
        return f"{enum_name}.{enum_member_name(str(value))}"
    if kind == "bool":
        return "True" if value else "False"
    if kind == "float":
        return repr(float(value))
    if kind in ("int", "str"):
        return repr(value)
    raise SpecError(f"unsupported default for kind {kind!r}")
