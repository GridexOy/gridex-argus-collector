"""Identifier and literal helpers shared by the model builder and the renderers."""

from __future__ import annotations

import json
import re

_WORD = re.compile(r"[A-Za-z0-9]+")
_CAMEL_BOUNDARY = re.compile(r"(?<!^)(?=[A-Z])")
_NON_IDENTIFIER = re.compile(r"[^A-Za-z0-9]+")


def pascal_case(name: str) -> str:
    """snake_case, camelCase or dotted name -> PascalCase (for a class name part)."""
    return "".join(word[:1].upper() + word[1:] for word in _WORD.findall(name))


def snake_case(name: str) -> str:
    """PascalCase schema name, camelCase operationId or `X-Header-Name` -> snake_case."""
    spaced = _CAMEL_BOUNDARY.sub("_", name)
    return _NON_IDENTIFIER.sub("_", spaced).strip("_").lower()


def enum_member_name(value: str) -> str:
    """OpenAPI enum string value -> a valid, readable StrEnum member identifier."""
    cleaned = _NON_IDENTIFIER.sub("_", value).strip("_").upper()
    if not cleaned:
        raise ValueError(f"enum value {value!r} has no identifier characters")
    if cleaned[0].isdigit():
        cleaned = "_" + cleaned
    return cleaned


def py_literal(value: object) -> str:
    """A JSON scalar -> Python source for the same value (strings double-quoted)."""
    if value is None or isinstance(value, bool):
        return repr(value)
    if isinstance(value, int | float):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value)
    raise ValueError(f"no Python literal for {value!r}")


def py_scalar_name(value: object) -> str:
    """The Python scalar type of a JSON scalar value (for a `const` field)."""
    for scalar in (bool, int, float, str):
        if isinstance(value, scalar):
            return scalar.__name__
    raise ValueError(f"unsupported const value {value!r}")
