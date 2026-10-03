"""Pure rules of the diagnostics module.

The same rules live in `scripts/diagnose.ps1`; `parse_report_json` checks
that the states the script reported match these rules, so any drift
between the two implementations surfaces as an error instead of silence.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

SCHEMA = "argus-collector-diagnose/1"
DISK_LOW_PCT = 85
GPU_MODEL_MIN_USED_MB = 1024


class ChromeState(StrEnum):
    AVAILABLE = "available"
    MISSING = "missing"


class GpuState(StrEnum):
    NVIDIA = "nvidia"
    OTHER = "other"
    MISSING = "missing"


class DiskState(StrEnum):
    OK = "ok"
    LOW = "low"


class ModelState(StrEnum):
    GPU = "gpu"
    CPU = "cpu"
    NONE = "none"


@dataclass(frozen=True)
class Facts:
    os_name: str
    os_version: str
    chrome_path: str
    chrome_version: str
    gpu_name: str
    gpu_driver: str
    gpu_memory_total_mb: int
    gpu_memory_used_mb: int
    gpu_source: str
    memory_total_mb: int
    memory_free_mb: int
    disk_path: str
    disk_total_gb: float
    disk_free_gb: float
    model_endpoint: str
    model_reachable: bool
    model_detail: str


@dataclass(frozen=True)
class States:
    chrome: ChromeState
    gpu: GpuState
    disk: DiskState
    model: ModelState
    disk_used_pct: int


@dataclass(frozen=True)
class Report:
    facts: Facts
    states: States
    source: str


def disk_used_pct(total_gb: float, free_gb: float) -> int:
    if total_gb <= 0:
        return 0
    return round((total_gb - free_gb) * 100 / total_gb)


def gpu_state(name: str) -> GpuState:
    if not name:
        return GpuState.MISSING
    return GpuState.NVIDIA if "nvidia" in name.lower() else GpuState.OTHER


def model_state(reachable: bool, gpu: GpuState, gpu_used_mb: int) -> ModelState:
    if not reachable:
        return ModelState.NONE
    if gpu is GpuState.NVIDIA and gpu_used_mb >= GPU_MODEL_MIN_USED_MB:
        return ModelState.GPU
    return ModelState.CPU


def derive_states(facts: Facts) -> States:
    gpu = gpu_state(facts.gpu_name)
    used = disk_used_pct(facts.disk_total_gb, facts.disk_free_gb)
    return States(
        chrome=ChromeState.AVAILABLE if facts.chrome_path else ChromeState.MISSING,
        gpu=gpu,
        disk=DiskState.LOW if used > DISK_LOW_PCT else DiskState.OK,
        model=model_state(facts.model_reachable, gpu, facts.gpu_memory_used_mb),
        disk_used_pct=used,
    )


def facts_from_json(data: dict[str, Any]) -> Facts:
    """Map the diagnose.ps1 JSON document to Facts (raises KeyError/ValueError)."""
    os_, chrome, gpu = data["os"], data["chrome"], data["gpu"]
    memory, disk, model = data["memory"], data["disk"], data["model"]
    return Facts(
        os_name=str(os_["name"]),
        os_version=str(os_["version"]),
        chrome_path=str(chrome["path"]),
        chrome_version=str(chrome["version"]),
        gpu_name=str(gpu["name"]),
        gpu_driver=str(gpu["driver"]),
        gpu_memory_total_mb=int(gpu["memory_total_mb"]),
        gpu_memory_used_mb=int(gpu["memory_used_mb"]),
        gpu_source=str(gpu["source"]),
        memory_total_mb=int(memory["total_mb"]),
        memory_free_mb=int(memory["free_mb"]),
        disk_path=str(disk["path"]),
        disk_total_gb=float(disk["total_gb"]),
        disk_free_gb=float(disk["free_gb"]),
        model_endpoint=str(model["endpoint"]),
        model_reachable=bool(model["reachable"]),
        model_detail=str(model["detail"]),
    )


def reported_states(data: dict[str, Any]) -> dict[str, str]:
    return {k: str(data[k]["state"]) for k in ("chrome", "gpu", "disk", "model")}


def parse_report_json(text: str, source: str) -> Report:
    """Parse diagnose.ps1 -Json output and verify its states against the rules."""
    data = json.loads(text)
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        raise ValueError(f"diagnose output is not {SCHEMA}")
    facts = facts_from_json(data)
    states = derive_states(facts)
    expected = {
        "chrome": states.chrome.value,
        "gpu": states.gpu.value,
        "disk": states.disk.value,
        "model": states.model.value,
    }
    got = reported_states(data)
    if got != expected:
        raise ValueError(f"diagnose states {got} differ from rules {expected}")
    return Report(facts=facts, states=states, source=source)


def report_to_json(report: Report) -> str:
    """Serialise a Python-collected report in the diagnose.ps1 document shape."""
    f, s = report.facts, report.states
    doc = {
        "schema": SCHEMA,
        "source": report.source,
        "os": {"name": f.os_name, "version": f.os_version},
        "chrome": {"path": f.chrome_path, "version": f.chrome_version, "state": s.chrome.value},
        "gpu": {
            "name": f.gpu_name,
            "driver": f.gpu_driver,
            "memory_total_mb": f.gpu_memory_total_mb,
            "memory_used_mb": f.gpu_memory_used_mb,
            "source": f.gpu_source,
            "state": s.gpu.value,
        },
        "memory": {"total_mb": f.memory_total_mb, "free_mb": f.memory_free_mb},
        "disk": {
            "path": f.disk_path,
            "total_gb": f.disk_total_gb,
            "free_gb": f.disk_free_gb,
            "used_pct": s.disk_used_pct,
            "state": s.disk.value,
        },
        "model": {
            "endpoint": f.model_endpoint,
            "reachable": f.model_reachable,
            "detail": f.model_detail,
            "state": s.model.value,
        },
    }
    return json.dumps(doc, indent=2)
