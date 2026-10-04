"""FieldSpec -> Python type / (de)serialization expression rendering.

Shared by render_service (class bodies, to_json/from_json bodies) so the
mapping from a field's `kind` to Python code lives in exactly one place.
"""

from __future__ import annotations

from codegen.naming import pascal_to_snake
from codegen.types import FieldSpec

SCALAR_CAST = ("str", "int", "float", "bool")  # also valid as a Python cast expression


def json_key(field: FieldSpec) -> str:
    return f'"{field.name}"'


def field_type(field: FieldSpec) -> str:
    base, nullable_by_kind = _base_type(field)
    nullable = nullable_by_kind or (not field.required and field.default_literal == "None")
    return f"{base} | None" if nullable else base


def _base_type(field: FieldSpec) -> tuple[str, bool]:
    kind = field.kind
    if kind.endswith("_or_null"):
        return kind[: -len("_or_null")], True
    if kind in SCALAR_CAST:
        return kind, False
    if kind in ("enum", "object"):
        assert field.ref is not None
        return field.ref, False
    if kind == "list_scalar":
        assert field.scalar is not None
        return f"list[{field.scalar}]", False
    if kind == "list_object":
        assert field.ref is not None
        return f"list[{field.ref}]", False
    raise ValueError(f"unknown field kind {kind!r}")


def to_json_expr(field: FieldSpec) -> str:
    value = f"value.{field.name}"
    kind = field.kind
    if kind in SCALAR_CAST or kind.endswith("_or_null"):
        return value
    if kind == "enum":
        return f"{value}.value"
    if kind == "object":
        assert field.ref is not None
        return f"{pascal_to_snake(field.ref)}_to_json({value})"
    if kind == "list_scalar":
        return f"list({value})"
    if kind == "list_object":
        assert field.ref is not None
        return f"[{pascal_to_snake(field.ref)}_to_json(v) for v in {value}]"
    raise ValueError(f"unknown field kind {kind!r}")


def omit_condition(field: FieldSpec) -> str:
    """Condition under which an optional field IS included on the wire."""
    value = f"value.{field.name}"
    if field.default_literal == "None":
        return f"{value} is not None"
    if field.kind == "bool":
        # `!= True`/`!= False` is ruff E712; identity is the idiomatic bool check.
        return f"{value} is not {field.default_literal}"
    return f"{value} != {field.default_literal}"


def _cast_expr(field: FieldSpec, data_expr: str) -> str:
    kind = field.kind
    if kind in SCALAR_CAST:
        return f"{kind}({data_expr})"
    if kind.endswith("_or_null"):
        scalar = kind[: -len("_or_null")]
        return f"{scalar}({data_expr}) if {data_expr} is not None else None"
    if kind == "enum":
        return f"{field.ref}({data_expr})"
    if kind == "object":
        assert field.ref is not None
        return f"{pascal_to_snake(field.ref)}_from_json({data_expr})"
    if kind == "list_scalar":
        assert field.scalar is not None
        return f"[{field.scalar}(v) for v in {data_expr}]"
    if kind == "list_object":
        assert field.ref is not None
        return f"[{pascal_to_snake(field.ref)}_from_json(v) for v in {data_expr}]"
    raise ValueError(f"unknown field kind {kind!r}")


def from_json_expr(field: FieldSpec) -> str:
    key_expr = f"data[{json_key(field)}]"
    cast = _cast_expr(field, key_expr)
    if field.required:
        return cast
    # A conditional expression used as the true-branch of another one needs
    # parens (Python grammar only allows an unparenthesized ternary in the
    # else-branch position).
    if " if " in cast:
        cast = f"({cast})"
    return f"{cast} if {json_key(field)} in data else {field.default_literal}"
