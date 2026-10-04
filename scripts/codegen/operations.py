"""Turn each manifest operationId into an OperationSpec (signature parameters, body, schemas).

Python parameters follow the operation, in this order: path parameters (in
path order), header parameters (document order), then either one JSON
`request` or one parameter per multipart/form-data property. Every 2xx
response must share one schema; the `default` response is the error schema.
"""

from __future__ import annotations

import re

from codegen.naming import pascal_case, snake_case
from codegen.spec import (
    JSON_MEDIA,
    JsonDict,
    SpecError,
    error_schema_ref,
    find_operation,
    parameters,
    request_body,
    resolve_ref,
    security_scheme,
    success_schema_ref,
)
from codegen.types import OperationSpec, ParamSpec, TypeRef
from codegen.walker import SchemaWalker

PLACEHOLDER = re.compile(r"\{([^}]+)\}")
RESERVED = {"base_url", "token", "request", "proxy_mode", "timeout_s"}


def build_operation(walker: SchemaWalker, operation_id: str) -> OperationSpec:
    path, method, operation = find_operation(walker.spec, operation_id)
    if method != "post":
        raise SpecError(f"{operation_id}: only POST operations are supported")
    for location in ("query", "cookie"):
        if parameters(operation, location):
            raise SpecError(f"{operation_id}: {location} parameters are not supported")
    params = _path_params(walker, path, operation) + _header_params(walker, operation)
    media, schema, encoding = request_body(operation)
    request_schema = ""
    if media == JSON_MEDIA:
        request_schema = _object_ref(walker, schema, operation_id)
    else:
        params += _multipart_params(walker, schema, encoding, operation_id)
    _check_names(params, operation_id)
    return OperationSpec(
        operation_id=operation_id,
        func_name=snake_case(operation_id),
        path=path,
        method=method,
        security_scheme=security_scheme(walker.spec, operation),
        params=tuple(params),
        body="json" if media == JSON_MEDIA else "multipart",
        request_schema=request_schema,
        response_schema=_object_ref(walker, {"$ref": success_schema_ref(operation)}, operation_id),
        error_schema=_object_ref(walker, {"$ref": error_schema_ref(operation)}, operation_id),
    )


def _object_ref(walker: SchemaWalker, schema: JsonDict, operation_id: str) -> str:
    if "$ref" not in schema:
        raise SpecError(f"{operation_id}: request/response schemas must be $refs")
    ref = walker.component(schema["$ref"])
    if ref.kind != "object":
        raise SpecError(f"{operation_id}: {schema['$ref']} is not an object schema")
    return ref.name


def _path_params(walker: SchemaWalker, path: str, operation: JsonDict) -> list[ParamSpec]:
    declared = {param["name"]: param for param in parameters(operation, "path")}
    names = PLACEHOLDER.findall(path)
    if set(names) != set(declared):
        raise SpecError(f"{path}: path placeholders and path parameters differ")
    return [_string_param(walker, declared[name], "path") for name in names]


def _header_params(walker: SchemaWalker, operation: JsonDict) -> list[ParamSpec]:
    return [_string_param(walker, param, "header") for param in parameters(operation, "header")]


def _string_param(walker: SchemaWalker, param: JsonDict, location: str) -> ParamSpec:
    name = str(param["name"])
    if not param.get("required"):
        raise SpecError(f"{location} parameter {name!r}: only required parameters are supported")
    param_type = walker.type_of(param.get("schema") or {}, pascal_case(name))
    if param_type != TypeRef("scalar", "str"):
        raise SpecError(f"{location} parameter {name!r}: only string parameters are supported")
    return ParamSpec(snake_case(name), name, location, param_type)


def _multipart_params(
    walker: SchemaWalker, schema: JsonDict, encoding: JsonDict, operation_id: str
) -> list[ParamSpec]:
    """One parameter per multipart property; the wrapper schema itself gets no class."""
    owner, wrapper = resolve_ref(walker.spec, schema["$ref"]) if "$ref" in schema else ("", schema)
    props: JsonDict = wrapper.get("properties") or {}
    if not props or set(wrapper.get("required") or []) != set(props):
        raise SpecError(f"{operation_id}: every multipart property must be required")
    params = []
    for name, node in props.items():
        part_type = walker.type_of(node, owner + pascal_case(name))
        if part_type.kind == "bytes":
            params.append(ParamSpec(snake_case(name), name, "file_part", part_type))
        elif part_type.kind == "object":
            content_type = (encoding.get(name) or {}).get("contentType", JSON_MEDIA)
            params.append(ParamSpec(snake_case(name), name, "json_part", part_type, content_type))
        else:
            raise SpecError(f"{operation_id}: multipart part {name!r} must be binary or an object")
    return params


def _check_names(params: list[ParamSpec], operation_id: str) -> None:
    names = [param.name for param in params]
    names += [f"{param.name}_content_type" for param in params if param.location == "file_part"]
    if len(set(names)) != len(names) or RESERVED & set(names):
        raise SpecError(f"{operation_id}: parameter names {names} collide")
