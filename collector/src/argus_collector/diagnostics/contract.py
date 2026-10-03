"""Single entry point of the `diagnostics` module.

`collect()` returns the same report the owner sees from
`scripts/diagnose.ps1`: on Windows it runs that script with `-Json`,
elsewhere it probes with Python so the panel and tests work in CI.
"""

from __future__ import annotations

import os
from pathlib import Path

from argus_collector.diagnostics import repository, service
from argus_collector.diagnostics.repository import DiagnosticsError
from argus_collector.diagnostics.service import (
    ChromeState,
    DiskState,
    Facts,
    GpuState,
    ModelState,
    Report,
    States,
)
from argus_collector.runtime import contract as runtime

__all__ = [
    "ChromeState",
    "DiagnosticsError",
    "DiskState",
    "Facts",
    "GpuState",
    "ModelState",
    "Report",
    "States",
    "collect",
    "parse_report_json",
    "report_to_json",
]

DEFAULT_MODEL_ENDPOINT = "http://127.0.0.1:8080"
DIAGNOSE_SCRIPT = Path("scripts") / "diagnose.ps1"
SOURCE_POWERSHELL = "diagnose.ps1"
SOURCE_PYTHON = "python"


def parse_report_json(text: str, source: str = SOURCE_POWERSHELL) -> Report:
    return service.parse_report_json(text, source)


def report_to_json(report: Report) -> str:
    return service.report_to_json(report)


def collect(
    model_endpoint: str = DEFAULT_MODEL_ENDPOINT, use_powershell: bool | None = None
) -> Report:
    """Collect facts and derive states. Raises DiagnosticsError on Windows failures."""
    if use_powershell is None:
        use_powershell = os.name == "nt"
    if use_powershell:
        script = runtime.repo_root() / DIAGNOSE_SCRIPT
        text = repository.run_powershell_diagnose(script, model_endpoint)
        try:
            return service.parse_report_json(text, SOURCE_POWERSHELL)
        except (ValueError, KeyError) as exc:
            raise DiagnosticsError(f"{script.name} output rejected: {exc}") from exc
    disk_path = runtime.user_data_dir().anchor or Path.home()
    facts = repository.python_facts(model_endpoint, Path(disk_path))
    return Report(facts=facts, states=service.derive_states(facts), source=SOURCE_PYTHON)
