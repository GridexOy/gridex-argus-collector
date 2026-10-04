"""TypeRef -> Python annotation and (de)serialization expressions.

Each function records the names its output uses in a Needs, so the file the
expression lands in imports exactly what it needs. `dump`/`parse` return an
inline expression over a value; `dumper`/`parser` return the callable form
used as an argument of the wire.py helpers (`opt`, `or_none`, `list_of`...).
"""

from __future__ import annotations

from codegen.chunking import Needs
from codegen.naming import snake_case
from codegen.types import FieldSpec, TypeRef

NAMED = ("enum", "object", "union")
ANY = ("typing", "Any")
IDENTITY = ("scalar", "any", "bytes")
SIMPLE_ITEMS = ("scalar", "any", "dict", "enum", "object", "union")


def codec_name(type_name: str, direction: str) -> str:
    """`ClaimRequest`, "to" -> `claim_request_to_json`."""
    return f"{snake_case(type_name)}_{direction}_json"


def annotation(t: TypeRef, needs: Needs) -> str:
    if t.kind in ("scalar", "bytes"):
        return "bytes" if t.kind == "bytes" else t.name
    if t.kind in ("any", "dict"):
        needs.stdlib.add(ANY)
        return "Any" if t.kind == "any" else "dict[str, Any]"
    if t.kind in NAMED:
        needs.types.add(t.name)
        return t.name
    if t.kind == "list":
        return f"list[{annotation(_item(t), needs)}]"
    if t.kind == "nullable":
        return f"{annotation(_item(t), needs)} | None"
    raise ValueError(f"unknown type kind {t.kind!r}")


def field_annotation(field: FieldSpec, needs: Needs) -> str:
    base = annotation(field.type, needs)
    implicit_none = not field.const and not field.required and field.default == "None"
    if implicit_none and field.type.kind not in ("nullable", "any"):
        return f"{base} | None"
    return base


def omit_condition(field: FieldSpec) -> str:
    """Condition under which an optional field IS written to the wire."""
    value = f"value.{field.name}"
    if field.default == "None":
        return f"{value} is not None"
    if field.default in ("True", "False"):
        # `!= True` is ruff E712; identity is the idiomatic bool check.
        return f"{value} is not {field.default}"
    return f"{value} != {field.default}"


def dump(t: TypeRef, value: str, needs: Needs) -> str:
    """Inline expression turning `value` (of type t) into its JSON form."""
    if t.kind in IDENTITY:
        return value
    if t.kind == "dict":
        return f"dict({value})"
    if t.kind == "enum":
        return f"{value}.value"
    if t.kind in ("object", "union"):
        return f"{_codec(t.name, 'to', needs)}({value})"
    item = _item(t)
    if t.kind == "list" and item.kind not in SIMPLE_ITEMS:
        return f"{_wire('list_of', needs)}({dumper(item, needs)})({value})"
    if t.kind == "list":
        inner = dump(item, "v", needs)
        return f"list({value})" if inner == "v" else f"[{inner} for v in {value}]"
    if item.kind in IDENTITY:
        return value
    return f"{_wire('or_none', needs)}({value}, {dumper(item, needs)})"


def dumper(t: TypeRef, needs: Needs) -> str:
    if t.kind in IDENTITY:
        return _wire("any_value", needs)
    if t.kind == "dict":
        return _wire("json_object", needs)
    if t.kind == "enum":
        return _wire("enum_value", needs)
    if t.kind in ("object", "union"):
        return _codec(t.name, "to", needs)
    helper = "list_of" if t.kind == "list" else "nullable"
    return f"{_wire(helper, needs)}({dumper(_item(t), needs)})"


def parse(t: TypeRef, raw: str, needs: Needs) -> str:
    """Inline expression turning the JSON value `raw` into a value of type t."""
    if t.kind == "scalar":
        return f"{t.name}({raw})"
    if t.kind == "any":
        return raw
    if t.kind == "dict":
        return f"dict({raw})"
    if t.kind in NAMED:
        return f"{parser(t, needs)}({raw})"
    item = _item(t)
    if t.kind == "list" and item.kind in SIMPLE_ITEMS:
        inner = parse(item, "v", needs)
        return f"list({raw})" if inner == "v" else f"[{inner} for v in {raw}]"
    if t.kind == "list":
        return f"{parser(t, needs)}({raw})"
    if t.kind == "nullable" and item.kind == "any":
        return raw
    if t.kind == "nullable":
        return f"{_wire('or_none', needs)}({raw}, {parser(item, needs)})"
    raise ValueError(f"type kind {t.kind!r} cannot be read from JSON")


def parser(t: TypeRef, needs: Needs) -> str:
    if t.kind == "scalar":
        return t.name
    if t.kind == "any":
        return _wire("any_value", needs)
    if t.kind == "dict":
        return _wire("json_object", needs)
    if t.kind == "enum":
        needs.types.add(t.name)
        return t.name
    if t.kind in ("object", "union"):
        return _codec(t.name, "from", needs)
    if t.kind in ("list", "nullable"):
        helper = "list_of" if t.kind == "list" else "nullable"
        return f"{_wire(helper, needs)}({parser(_item(t), needs)})"
    raise ValueError(f"type kind {t.kind!r} cannot be read from JSON")


def _item(t: TypeRef) -> TypeRef:
    if t.item is None:
        raise ValueError(f"{t.kind} type without an item type")
    return t.item


def _codec(type_name: str, direction: str, needs: Needs) -> str:
    name = codec_name(type_name, direction)
    needs.codecs.add(name)
    return name


def _wire(helper: str, needs: Needs) -> str:
    needs.fixed.add(("wire", helper))
    return helper
