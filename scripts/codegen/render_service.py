"""Render api_client/service.py: dataclasses and StrEnums only.

Pure (de)serialization for these types is rendered separately into
serialization.py by render_serialization.py -- splitting the two keeps both
generated files under this repo's 200-line file-size gate.
"""

from __future__ import annotations

from codegen.naming import enum_member_name
from codegen.pytypes import field_type
from codegen.types import ClientModel, EnumSpec, FieldSpec, ObjectSpec

HEADER = '''"""Generated dataclasses/StrEnums for the api_client module (mechanically generated).

Source: {source}.
Do not edit by hand -- see api_client/README.md to regenerate.
Pure (de)serialization for these types lives in serialization.py, split out
to stay under this repo's file-size gate.
"""

from __future__ import annotations

from dataclasses import dataclass
{enum_import}'''


def render_service(model: ClientModel, source_rel: str) -> str:
    enum_import = "from enum import StrEnum\n" if model.enums else ""
    blocks = [HEADER.format(source=source_rel, enum_import=enum_import).rstrip()]
    for enum in model.enums:
        blocks.append("\n".join(_render_enum(enum)))
    for obj in model.objects:
        blocks.append("\n".join(_render_dataclass(obj)))
    return "\n\n\n".join(blocks).rstrip() + "\n"


def _render_enum(enum: EnumSpec) -> list[str]:
    lines = [f"class {enum.name}(StrEnum):"]
    for value in enum.values:
        lines.append(f'    {enum_member_name(value)} = "{value}"')
    return lines


def _render_dataclass(obj: ObjectSpec) -> list[str]:
    lines = ["@dataclass(frozen=True)", f"class {obj.name}:"]
    for field in obj.fields:
        lines.append(_class_field_line(field))
    return lines


def _class_field_line(field: FieldSpec) -> str:
    type_str = field_type(field)
    if field.required:
        return f"    {field.name}: {type_str}"
    return f"    {field.name}: {type_str} = {field.default_literal}"
