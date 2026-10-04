"""Minimal JSON Schema validator for the OpenAPI component schemas (one door).

Covers exactly the keywords the contract uses: `$ref`, `type` (one name or a
list, incl. `null`), `enum`, `const`, `oneOf` (exactly one branch),
`properties` / `required` / `additionalProperties` (false, true, `{}` or a
schema), `items`, `minItems` / `maxItems`, `minLength` / `maxLength`,
`minimum` / `maximum`, `pattern`, and `format` `uri` (scheme + netloc) and
`date-time` (RFC 3339 with offset, `Z` allowed). A bool is never an integer
or number. Errors are strings prefixed with a JSON path (`$.a[0].b`).
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable
from datetime import datetime
from typing import Any
from urllib.parse import urlsplit

Schema = dict[str, Any]
Resolver = Callable[[str], Schema]

DATE_TIME = re.compile(r"^\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(\.\d+)?([Zz]|[+-]\d{2}:\d{2})$")


def validate(instance: Any, schema: Schema, resolve: Resolver, path: str = "$") -> list[str]:
    """Every violation of `schema` by `instance`; an empty list means valid."""
    errors: list[str] = []
    _check(instance, schema, resolve, path, errors)
    return errors


def same(left: Any, right: Any) -> bool:
    """JSON equality: a bool never equals a number."""
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(same(left[k], right[k]) for k in left)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(same(a, b) for a, b in zip(left, right, strict=True))
    return bool(left == right)


def is_type(value: Any, name: str) -> bool:
    if name == "null":
        return value is None
    if name == "boolean":
        return isinstance(value, bool)
    if name == "object":
        return isinstance(value, dict)
    if name == "array":
        return isinstance(value, list)
    if name == "string":
        return isinstance(value, str)
    if isinstance(value, bool) or not isinstance(value, int | float):
        return False
    if isinstance(value, float) and not math.isfinite(value):
        return False
    if name == "integer":
        return isinstance(value, int) or value.is_integer()
    return name == "number"


def format_ok(value: str, fmt: str) -> bool:
    if fmt == "uri":
        try:
            parts = urlsplit(value)
        except ValueError:
            return False
        return bool(parts.scheme) and bool(parts.netloc)
    if fmt == "date-time":
        if not DATE_TIME.match(value):
            return False
        try:
            datetime.fromisoformat(value.upper())
        except ValueError:
            return False
    return True


def _type_name(value: Any) -> str:
    for name in ("null", "boolean", "integer", "number", "string", "array", "object"):
        if is_type(value, name):
            return name
    return type(value).__name__


def _check(value: Any, schema: Schema, resolve: Resolver, path: str, errors: list[str]) -> None:
    if "$ref" in schema:
        _check(value, resolve(schema["$ref"]), resolve, path, errors)
    if "oneOf" in schema:
        _check_one_of(value, schema["oneOf"], resolve, path, errors)
    if "type" in schema:
        names = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(is_type(value, name) for name in names):
            errors.append(f"{path}: expected {'|'.join(names)}, got {_type_name(value)}")
            return
    if "const" in schema and not same(value, schema["const"]):
        errors.append(f"{path}: must equal {schema['const']!r}")
    if "enum" in schema and not any(same(value, option) for option in schema["enum"]):
        errors.append(f"{path}: {value!r} is not one of {schema['enum']}")
    if isinstance(value, dict):
        _check_object(value, schema, resolve, path, errors)
    elif isinstance(value, list):
        _check_array(value, schema, resolve, path, errors)
    elif isinstance(value, str):
        _check_string(value, schema, path, errors)
    elif is_type(value, "number"):
        _check_number(value, schema, path, errors)


def _check_one_of(
    value: Any, options: list[Schema], resolve: Resolver, path: str, errors: list[str]
) -> None:
    results = [validate(value, option, resolve, path) for option in options]
    matches = sum(1 for result in results if not result)
    if matches == 1:
        return
    if matches > 1:
        errors.append(f"{path}: matches {matches} oneOf branches, expected exactly 1")
        return
    errors.append(f"{path}: matches no oneOf branch")
    errors.extend(sorted(results, key=len)[0])


def _check_object(
    value: dict[str, Any], schema: Schema, resolve: Resolver, path: str, errors: list[str]
) -> None:
    properties: dict[str, Schema] = schema.get("properties", {})
    for name in schema.get("required", []):
        if name not in value:
            errors.append(f"{path}: missing required property '{name}'")
    extra = schema.get("additionalProperties", True)
    for key, item in value.items():
        if key in properties:
            _check(item, properties[key], resolve, f"{path}.{key}", errors)
        elif extra is False:
            errors.append(f"{path}: unexpected property '{key}'")
        elif isinstance(extra, dict) and extra:
            _check(item, extra, resolve, f"{path}.{key}", errors)


def _check_array(
    value: list[Any], schema: Schema, resolve: Resolver, path: str, errors: list[str]
) -> None:
    if "minItems" in schema and len(value) < schema["minItems"]:
        errors.append(f"{path}: needs at least {schema['minItems']} items, has {len(value)}")
    if "maxItems" in schema and len(value) > schema["maxItems"]:
        errors.append(f"{path}: allows at most {schema['maxItems']} items, has {len(value)}")
    items = schema.get("items")
    if isinstance(items, dict):
        for index, item in enumerate(value):
            _check(item, items, resolve, f"{path}[{index}]", errors)


def _check_string(value: str, schema: Schema, path: str, errors: list[str]) -> None:
    if "minLength" in schema and len(value) < schema["minLength"]:
        errors.append(f"{path}: shorter than {schema['minLength']} characters")
    if "maxLength" in schema and len(value) > schema["maxLength"]:
        errors.append(f"{path}: longer than {schema['maxLength']} characters")
    if "pattern" in schema and not re.search(schema["pattern"], value):
        errors.append(f"{path}: does not match pattern {schema['pattern']!r}")
    if "format" in schema and not format_ok(value, schema["format"]):
        errors.append(f"{path}: {value!r} is not a valid {schema['format']}")


def _check_number(value: float, schema: Schema, path: str, errors: list[str]) -> None:
    if "minimum" in schema and value < schema["minimum"]:
        errors.append(f"{path}: {value} is below the minimum {schema['minimum']}")
    if "maximum" in schema and value > schema["maximum"]:
        errors.append(f"{path}: {value} is above the maximum {schema['maximum']}")
