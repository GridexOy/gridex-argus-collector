"""Plain data shapes the generator passes between spec.py, model.py and the renderers.

Kept separate from model.py (which builds these) purely to stay under the
house file-size gate once the dataclasses and the BFS/field-classification
logic are both counted in one file.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

SCALAR_JSON_TO_PY = {"string": "str", "integer": "int", "number": "float", "boolean": "bool"}
Enqueue = Callable[[str], None]


@dataclass(frozen=True)
class EnumSpec:
    name: str
    values: tuple[str, ...]


@dataclass(frozen=True)
class FieldSpec:
    name: str
    required: bool
    kind: str  # str|int|float|bool|<kind>_or_null|enum|object|list_scalar|list_object
    ref: str | None  # enum/object class name, for "enum"/"object"/"list_object"
    scalar: str | None  # python scalar type name, for "list_scalar"
    default_literal: str | None  # python source for a non-required field's default


@dataclass(frozen=True)
class ObjectSpec:
    name: str
    fields: tuple[FieldSpec, ...]


@dataclass(frozen=True)
class OperationSpec:
    operation_id: str
    path: str
    method: str
    security_scheme: str
    request_schema: str
    response_schema: str
    error_schema: str


@dataclass(frozen=True)
class ClientModel:
    enums: tuple[EnumSpec, ...]
    objects: tuple[ObjectSpec, ...]
    operations: tuple[OperationSpec, ...]
