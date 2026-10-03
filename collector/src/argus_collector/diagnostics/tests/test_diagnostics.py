"""Unit tests for diagnostics rules, JSON parsing and the Python probes."""

from __future__ import annotations

import json
from typing import Any

import pytest

from argus_collector.diagnostics import contract, service
from argus_collector.diagnostics.service import ChromeState, DiskState, GpuState, ModelState


def sample_document() -> dict[str, Any]:
    """Document in the exact shape scripts/diagnose.ps1 -Json prints on MAIN-PC."""
    return {
        "schema": service.SCHEMA,
        "source": "diagnose.ps1",
        "os": {"name": "Microsoft Windows 11 Pro", "version": "10.0.26100"},
        "chrome": {
            "path": "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
            "version": "141.0.7390.65",
            "state": "available",
        },
        "gpu": {
            "name": "NVIDIA GeForce RTX 4090",
            "driver": "581.29",
            "memory_total_mb": 24564,
            "memory_used_mb": 512,
            "source": "nvidia-smi",
            "state": "nvidia",
        },
        "memory": {"total_mb": 65432, "free_mb": 40000},
        "disk": {"path": "C:", "total_gb": 1863.0, "free_gb": 900.5, "used_pct": 52, "state": "ok"},
        "model": {
            "endpoint": "http://127.0.0.1:11434/v1",
            "name": "qwen2.5:14b-instruct",
            "reachable": False,
            "detail": "no answer",
            "state": "none",
        },
    }


def test_disk_used_pct_rounds_and_handles_zero() -> None:
    assert service.disk_used_pct(100.0, 14.0) == 86
    assert service.disk_used_pct(0, 0) == 0


@pytest.mark.parametrize(
    ("name", "state"),
    [
        ("NVIDIA GeForce RTX 4090", GpuState.NVIDIA),
        ("Intel UHD", GpuState.OTHER),
        ("", GpuState.MISSING),
    ],
)
def test_gpu_state(name: str, state: GpuState) -> None:
    assert service.gpu_state(name) == state


def test_model_state_rules() -> None:
    assert service.model_state(False, GpuState.NVIDIA, 20000) is ModelState.NONE
    assert service.model_state(True, GpuState.NVIDIA, 20000) is ModelState.GPU
    assert service.model_state(True, GpuState.NVIDIA, 100) is ModelState.CPU
    assert service.model_state(True, GpuState.MISSING, 0) is ModelState.CPU


def test_parse_accepts_consistent_document() -> None:
    report = contract.parse_report_json(json.dumps(sample_document()))
    assert report.states.chrome is ChromeState.AVAILABLE
    assert report.states.gpu is GpuState.NVIDIA
    assert report.states.disk is DiskState.OK
    assert report.states.model is ModelState.NONE
    assert report.facts.gpu_memory_total_mb == 24564
    assert report.source == "diagnose.ps1"


def test_parse_rejects_state_drift() -> None:
    doc = sample_document()
    doc["chrome"]["state"] = "missing"
    with pytest.raises(ValueError, match="differ from rules"):
        contract.parse_report_json(json.dumps(doc))


def test_parse_rejects_wrong_schema() -> None:
    doc = sample_document()
    doc["schema"] = "something-else"
    with pytest.raises(ValueError, match="argus-collector-diagnose/1"):
        contract.parse_report_json(json.dumps(doc))


def test_low_disk_and_gpu_model() -> None:
    doc = sample_document()
    doc["disk"].update({"free_gb": 100.0, "used_pct": 95, "state": "low"})
    doc["model"].update({"reachable": True, "state": "gpu"})
    doc["gpu"]["memory_used_mb"] = 9000
    report = contract.parse_report_json(json.dumps(doc))
    assert report.states.disk is DiskState.LOW
    assert report.states.model is ModelState.GPU


def test_report_json_roundtrip() -> None:
    report = contract.parse_report_json(json.dumps(sample_document()))
    again = contract.parse_report_json(contract.report_to_json(report), "python")
    assert again.facts == report.facts
    assert again.states == report.states


def test_python_collect_runs_here() -> None:
    report = contract.collect("http://127.0.0.1:9/v1", use_powershell=False)
    assert report.source == "python"
    assert report.states.model is ModelState.NONE
    assert report.facts.model_name == "qwen2.5:14b-instruct"
    assert "no answer" in report.facts.model_detail
    assert report.facts.disk_total_gb > 0
    assert report.facts.memory_total_mb > 0
    assert report.facts.os_name


def test_model_listed_counts_as_reachable() -> None:
    from collector.tests.fake_model_server import FakeModelServer

    fake = FakeModelServer(lambda s, u: "{}").start()
    try:
        ok = contract.collect(fake.endpoint, "fake-instruct", use_powershell=False)
        other = contract.collect(fake.endpoint, "other", use_powershell=False)
    finally:
        fake.stop()
    assert ok.facts.model_reachable and ok.states.model is not ModelState.NONE
    assert not other.facts.model_reachable and other.states.model is ModelState.NONE
