"""Walk schemas depth-first from $refs and record every enum/object/union they define.

Generic: nothing here names a specific schema. A component keeps its own
name; an inline enum/object/union is named `<Owner><PropPascal>` (array items
add `Item`; a oneOf variant takes the PascalCase of its discriminator value).
A definition is recorded only after everything it uses (post-order), which
is exactly the order the renderers need. Recursive schemas are rejected.
"""

from __future__ import annotations

from codegen.naming import enum_member_name, pascal_case, py_literal, py_scalar_name
from codegen.spec import JsonDict, SpecError, resolve_ref
from codegen.types import SCALAR_JSON_TO_PY, EnumSpec, FieldSpec, ObjectSpec, TypeRef, UnionSpec

SCALAR_CAST = {"str": str, "int": int, "float": float, "bool": bool}
UNTYPED_KEYS = ("anyOf", "allOf", "properties", "items", "additionalProperties")


class SchemaWalker:
    def __init__(self, spec: JsonDict) -> None:
        self.spec = spec
        self.enums: dict[str, EnumSpec] = {}
        self.objects: dict[str, ObjectSpec] = {}
        self.unions: dict[str, UnionSpec] = {}
        self.order: list[str] = []
        self._components: dict[str, TypeRef] = {}
        self._in_progress: set[str] = set()

    def component(self, ref: str) -> TypeRef:
        name, schema = resolve_ref(self.spec, ref)
        if name in self._components:
            return self._components[name]
        if name in self._in_progress:
            raise SpecError(f"{name}: recursive schemas are not supported")
        self._in_progress.add(name)
        result = self.type_of(schema, name)
        self._in_progress.discard(name)
        self._components[name] = result
        return result

    def type_of(self, node: JsonDict, hint: str) -> TypeRef:
        """TypeRef of a schema node; an inline enum/object/union it defines is named `hint`."""
        if "$ref" in node:
            return self.component(node["$ref"])
        if "oneOf" in node:
            return self._one_of(node["oneOf"], hint)
        if "const" in node:
            raise SpecError(f"{hint}: `const` is only supported on an object property")
        json_type = node.get("type")
        if isinstance(json_type, list):
            return self._nullable_type(node, json_type, hint)
        if "enum" in node:
            return self._enum(node["enum"], hint)
        if json_type is None:
            if any(key in node for key in UNTYPED_KEYS):
                raise SpecError(f"{hint}: untyped schema with {sorted(node)} is not supported")
            return TypeRef("any")
        if json_type == "array":
            return TypeRef("list", item=self.type_of(node["items"], hint + "Item"))
        if json_type == "object":
            return self._object(node, hint)
        if json_type == "string" and node.get("format") == "binary":
            return TypeRef("bytes")
        if json_type in SCALAR_JSON_TO_PY:
            return TypeRef("scalar", SCALAR_JSON_TO_PY[json_type])
        raise SpecError(f"{hint}: unsupported JSON Schema type {json_type!r}")

    def _record(self, name: str) -> None:
        if name in self.order:
            raise SpecError(f"two different definitions are both named {name!r}")
        self.order.append(name)

    def _nullable_type(self, node: JsonDict, json_type: list[str], hint: str) -> TypeRef:
        non_null = [t for t in json_type if t != "null"]
        if len(non_null) != 1 or len(json_type) != 2:
            raise SpecError(f"{hint}: unsupported type list {json_type!r}")
        inner = {**node, "type": non_null[0]}
        if "enum" in node:
            inner["enum"] = [value for value in node["enum"] if value is not None]
        return TypeRef("nullable", item=self.type_of(inner, hint))

    def _enum(self, values: list[object], hint: str) -> TypeRef:
        named = tuple(value for value in values if value is not None)
        if not all(isinstance(value, str) for value in named):
            raise SpecError(f"{hint}: only string enums are supported")
        spec = EnumSpec(hint, tuple(str(value) for value in named))
        if self.enums.get(hint) != spec:
            self._record(hint)
            self.enums[hint] = spec
        ref = TypeRef("enum", hint)
        return TypeRef("nullable", item=ref) if None in values else ref

    def _object(self, node: JsonDict, hint: str) -> TypeRef:
        props: JsonDict = node.get("properties") or {}
        extra = node.get("additionalProperties", True)
        if not props:
            if extra is False:
                raise SpecError(f"{hint}: an object with no properties at all")
            return TypeRef("dict")
        if extra is not False:
            raise SpecError(f"{hint}: an object with properties needs additionalProperties: false")
        required = set(node.get("required") or [])
        fields = [self._field(hint, name, prop, name in required) for name, prop in props.items()]
        plain = [f for f in fields if not f.const]
        ordered = [f for f in plain if f.required] + [f for f in plain if not f.required]
        self._record(hint)
        self.objects[hint] = ObjectSpec(hint, tuple(ordered + [f for f in fields if f.const]))
        return TypeRef("object", hint)

    def _field(self, owner: str, prop: str, node: JsonDict, required: bool) -> FieldSpec:
        if "const" in node:
            value = node["const"]
            scalar = TypeRef("scalar", py_scalar_name(value))
            return FieldSpec(prop, scalar, required, py_literal(value), const=True)
        field_type = self.type_of(node, owner + pascal_case(prop))
        if required:
            return FieldSpec(prop, field_type, True)
        return FieldSpec(prop, field_type, False, _default_source(field_type, node, owner))

    def _one_of(self, variants: list[JsonDict], hint: str) -> TypeRef:
        non_null = [v for v in variants if v.get("type") != "null"]
        if len(non_null) != len(variants):
            if len(non_null) != 1 or len(variants) != 2:
                raise SpecError(f"{hint}: a nullable oneOf must be [<schema>, {{type: null}}]")
            return TypeRef("nullable", item=self.type_of(non_null[0], hint))
        shapes = [resolve_ref(self.spec, v["$ref"])[1] if "$ref" in v else v for v in variants]
        key = _discriminator(shapes, hint)
        members: list[tuple[str, str]] = []
        for variant, shape in zip(variants, shapes, strict=True):
            value = shape["properties"][key]["const"]
            ref = self.type_of(variant, hint + pascal_case(str(value)))
            if ref.kind != "object":
                raise SpecError(f"{hint}: every oneOf variant must be an object")
            members.append((py_literal(value), ref.name))
        self._record(hint)
        self.unions[hint] = UnionSpec(hint, key, tuple(members))
        return TypeRef("union", hint)


def _discriminator(shapes: list[JsonDict], hint: str) -> str:
    """The first property that is `const` in every variant, with distinct values."""
    for key, prop in (shapes[0].get("properties") or {}).items():
        if "const" not in prop:
            continue
        props = [(shape.get("properties") or {}).get(key) or {} for shape in shapes]
        if not all("const" in candidate for candidate in props):
            continue
        values = [candidate["const"] for candidate in props]
        if len(set(values)) == len(values):
            return str(key)
    raise SpecError(f"{hint}: oneOf variants share no distinct `const` discriminator")


def _default_source(field_type: TypeRef, node: JsonDict, owner: str) -> str:
    """Python source of an optional field's default: the schema's `default`, else None."""
    value = node.get("default")
    if value is None:
        return "None"
    target = field_type.item if field_type.kind == "nullable" and field_type.item else field_type
    if target.kind == "enum":
        return f"{target.name}.{enum_member_name(str(value))}"
    if target.kind == "scalar":
        return py_literal(SCALAR_CAST[target.name](value))
    raise SpecError(f"{owner}: unsupported default {value!r} (only scalars and enums)")
