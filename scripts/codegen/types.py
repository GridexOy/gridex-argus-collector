"""Plain data shapes the generator passes between spec.py, model.py and the renderers.

Kept separate from model.py (which builds these) purely to stay under the
house file-size gate.
"""

from __future__ import annotations

from dataclasses import dataclass

SCALAR_JSON_TO_PY = {"string": "str", "integer": "int", "number": "float", "boolean": "bool"}


@dataclass(frozen=True)
class TypeRef:
    """The Python shape of one schema node.

    kind: scalar (name = str|int|float|bool), bytes, any, dict, enum/object/union
    (name = generated class or alias), list or nullable (item = the inner type).
    """

    kind: str
    name: str = ""
    item: TypeRef | None = None


@dataclass(frozen=True)
class FieldSpec:
    name: str  # the JSON property name, used as the dataclass field name too
    type: TypeRef
    required: bool
    default: str | None = None  # Python source of the default (optional and const fields)
    const: bool = False  # a `const` property: always serialized, validated on parse


@dataclass(frozen=True)
class EnumSpec:
    name: str
    values: tuple[str, ...]


@dataclass(frozen=True)
class ObjectSpec:
    name: str
    fields: tuple[FieldSpec, ...]


@dataclass(frozen=True)
class UnionSpec:
    name: str
    discriminator: str  # the JSON property that is `const` (and distinct) in every variant
    variants: tuple[tuple[str, str], ...]  # (Python literal of the const value, object name)


@dataclass(frozen=True)
class ParamSpec:
    name: str  # Python parameter name
    wire_name: str  # path placeholder, header name or multipart part name
    location: str  # path | header | json_part | file_part
    type: TypeRef
    content_type: str = ""  # json_part only: the part's Content-Type


@dataclass(frozen=True)
class OperationSpec:
    operation_id: str
    func_name: str
    path: str
    method: str
    security_scheme: str
    params: tuple[ParamSpec, ...]  # path params, header params, multipart parts (in that order)
    body: str  # "json" or "multipart"
    request_schema: str  # the JSON body's schema name ("" for multipart)
    response_schema: str  # the one schema every 2xx response uses
    error_schema: str


@dataclass(frozen=True)
class ClientModel:
    enums: tuple[EnumSpec, ...]
    objects: tuple[ObjectSpec, ...]
    unions: tuple[UnionSpec, ...]
    order: tuple[str, ...]  # every enum/object/union name, dependencies first
    operations: tuple[OperationSpec, ...]
    error_schema: str
