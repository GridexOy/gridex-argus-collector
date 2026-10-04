# api_client

Generated from `docs/ARGUS20_COLLECTOR_OPENAPI.json` by `scripts/gen_api_client.ps1` (logic: `scripts/codegen/`).
Never edit the files below by hand -- rerun the generator; `check_codegen` fails
the build if a regeneration is not a no-op (CLAUDE.md rule 14, "one door").
Covers the operationIds in `scripts/codegen/manifest.py`: `heartbeat`, `claimJobs`, `uploadEvidence`, `postEvents`, `reconcileJob`.

| File | Contents |
|---|---|
| `contract.py` | the only entry point: re-exports types, codecs, `ApiError`, `ProxyMode`, ops |
| `service.py` | one function per operation: serialize, POST, parse any 2xx body |
| `repository.py` | `urllib.request` transport, `ApiError`, the `system`/`direct` openers |
| `multipart.py` | multipart/form-data encoding (no I/O) |
| `types_1..6.py` | `StrEnum`s, frozen dataclasses, union aliases (dependencies first) |
| `serialization_1..13.py` | `<snake>_to_json`/`_from_json` pairs, a class registry |
| `codec.py` | generic `to_json(value)` / `from_json(kind, data)` over the registries |
| `wire.py` | the small helpers the codecs share (`opt`, `const`, `or_none`, ...) |
| `tests/` | hand-written: codec round trips, an embedded `http.server` double |

Conventions:
- A component object is a frozen dataclass of the same name; field names are the
  JSON property names. Field order: required, then optional, then `const` fields.
- An optional property defaults to the schema's `default`, else `None`, and is left
  out of the JSON while it still equals that default. A `const` property is always
  written; reading it accepts a missing value but raises ValueError on another one.
- Inline enums/objects are named `<Schema><Prop>` (array items add `Item`); a
  component enum keeps its name. `oneOf` becomes a union alias whose variants are
  dispatched on the property that is `const` in each (`kind`, `type`); `oneOf`
  with `{type: null}` and `["T", "null"]` become `T | None`; `{}` becomes `Any`.
- Path parameters are percent-encoded; a multipart object part is sent as JSON.
- `proxy_mode` ("system" honors the OS proxy, "direct" never uses one) is a
  plain parameter the caller decides -- `api_client` never sniffs the host.

Regenerate: `pwsh scripts/gen_api_client.ps1` (or `scripts\gen_api_client.ps1`
from PowerShell). `git diff` must then be empty.
