"""Check pyproject.toml's import-linter forbidden_modules against the generated modules.

Only contract.py may be imported from outside api_client, so every other
generated module must be listed as forbidden; a regeneration that adds or
drops a chunk (`types_<n>.py`, `serialization_<n>.py`) must update that list.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from codegen.imports import PACKAGE

ENTRY_POINT = "contract"


def forbidden_mismatch(pyproject: Path, modules: list[str]) -> tuple[list[str], list[str]]:
    """(generated modules missing from forbidden_modules, listed modules that are not generated)."""
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    contracts = data.get("tool", {}).get("importlinter", {}).get("contracts", [])
    listed: set[str] = set()
    for contract in contracts:
        if contract.get("type") == "forbidden":
            listed |= {m for m in contract.get("forbidden_modules", []) if m.startswith(PACKAGE)}
    expected = {f"{PACKAGE}.{module}" for module in modules if module != ENTRY_POINT}
    return sorted(expected - listed), sorted(listed - expected)
