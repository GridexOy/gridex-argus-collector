"""Build the ClientModel (enums, dataclasses, unions, operations) reachable from the manifest.

Adding an operationId to manifest.MANIFEST and rerunning the generator is
enough to cover it: walker.py follows every $ref from the operation's
parameters, request body and responses, and records each definition after
the definitions it uses (the order the renderers emit them in).
"""

from __future__ import annotations

from collections.abc import Sequence

from codegen.operations import build_operation
from codegen.spec import JsonDict, SpecError
from codegen.types import ClientModel
from codegen.walker import SchemaWalker


def build_model(spec: JsonDict, manifest: Sequence[str]) -> ClientModel:
    walker = SchemaWalker(spec)
    operations = tuple(build_operation(walker, operation_id) for operation_id in manifest)
    errors = {op.error_schema for op in operations}
    if len(errors) != 1:
        raise SpecError(f"the manifest operations use different error schemas: {sorted(errors)}")
    return ClientModel(
        enums=tuple(walker.enums.values()),
        objects=tuple(walker.objects.values()),
        unions=tuple(walker.unions.values()),
        order=tuple(walker.order),
        operations=operations,
        error_schema=errors.pop(),
    )
