"""The small, explicit manifest of operationIds the generator covers today.

ARGUS20_TZ_TANDEM.md pair A1 ("Connection") only ever calls `heartbeat`; the
other ~8 operations in the OpenAPI document belong to later pairs (A2-A5) or
are SystemBearer/ARGUS-internal. Extend this list (and rerun
scripts/gen_api_client.ps1) when a later pair needs another operation --
nothing else in the generator needs to change for that to work.
"""

from __future__ import annotations

from pathlib import Path

MANIFEST: tuple[str, ...] = ("heartbeat",)
SPEC_RELATIVE_PATH = Path("docs") / "ARGUS20_COLLECTOR_OPENAPI.json"
