"""Identifier helpers shared by the model builder and the renderers."""

from __future__ import annotations

import re

_WORD = re.compile(r"[A-Za-z0-9]+")
_CAMEL_BOUNDARY = re.compile(r"(?<!^)(?=[A-Z])")


def pascal_case(name: str) -> str:
    """snake_case or camelCase property name -> PascalCase (for a class name part)."""
    return "".join(word.capitalize() for word in _WORD.findall(name))


def pascal_to_snake(name: str) -> str:
    """PascalCase schema name -> snake_case (for a generated function name part)."""
    return _CAMEL_BOUNDARY.sub("_", name).lower()


def enum_member_name(value: str) -> str:
    """OpenAPI enum string value -> a valid, readable StrEnum member identifier."""
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").upper()
    if not cleaned:
        raise ValueError(f"enum value {value!r} has no identifier characters")
    if cleaned[0].isdigit():
        cleaned = "_" + cleaned
    return cleaned
