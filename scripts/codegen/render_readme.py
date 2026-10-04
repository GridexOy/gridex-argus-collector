"""Render api_client/README.md (<= 40 lines, CLAUDE.md module rule)."""

from __future__ import annotations

from codegen.types import ClientModel

TEMPLATE = """# api_client

Generated from `{source}` by `scripts/gen_api_client.ps1`
(`scripts/gen_api_client.py` does the work; Python logic lives under
`scripts/codegen/`). Never edit the files below by hand -- rerun the
generator instead; `scripts/gates/check_codegen.py` fails the build if a
regeneration is not a no-op (CLAUDE.md rule 14, "one door").

Covers exactly the operationIds listed in `scripts/codegen/manifest.py`
(today: `{operations}` -- ARGUS20_TZ_TANDEM.md pair A1, "Connection"). The
other operations in the OpenAPI document belong to later pairs; extend the
manifest and rerun the generator when one of them is needed, nothing else
has to change by hand.

| File | Generated | Contents |
|---|---|---|
| `service.py` | yes | the dataclasses and `StrEnum`s |
| `serialization.py` | yes | `..._to_json`/`..._from_json` for required-only types (no I/O) |
| `serialization_patch.py` | yes | the same, for patch-style (any-optional-field) types |
| `repository.py` | yes | `urllib.request` transport, `ApiError`, the opener pair |
| `contract.py` | yes | re-exports the types, one wrapper function per op |
| `tests/test_api_client.py` | no | round-trip tests, an embedded `http.server` double |

Conventions the generator follows:
- A schema property required by the wire schema becomes a dataclass field
  with no default; the whole object is a frozen dataclass.
- A property outside `required` becomes a field defaulted to the schema's
  own `default` when it states one, else `None`. Serializing such an object
  (`PolicyPatch` today) omits every field still at its default/`None`, so
  the wire only ever carries what was actually set.
- `proxy_mode` ("system" honors the OS proxy, "direct" never uses one) is a
  plain parameter the caller decides -- `api_client` never sniffs the host.

Regenerate: `pwsh scripts/gen_api_client.ps1` (or `scripts\\gen_api_client.ps1`
from PowerShell). `git diff` must then be empty.
"""


def render_readme(model: ClientModel, source_rel: str) -> str:
    operations = ", ".join(op.operation_id for op in model.operations)
    return TEMPLATE.format(source=source_rel, operations=operations)
