"""Shared test helpers for the panel's tkinter tests."""

from __future__ import annotations

import time
import tkinter as tk
from collections.abc import Iterator
from typing import Any

import pytest

from argus_collector.ui.heartbeat_loop import HeartbeatLoop

TK_CREATE_RETRIES = 3
TK_CREATE_RETRY_DELAY_S = 0.3


@pytest.fixture(autouse=True)
def stop_heartbeat_clocks(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Every heartbeat clock a test starts stops with the test: the clocks are daemon
    threads and would otherwise write into the next test's journal."""
    started: list[HeartbeatLoop] = []
    original = HeartbeatLoop.ensure

    def ensure(loop: HeartbeatLoop) -> None:
        started.append(loop)
        original(loop)

    monkeypatch.setattr(HeartbeatLoop, "ensure", ensure)
    yield
    for loop in started:
        loop.stop()


def sample_document() -> dict[str, Any]:
    """Document in the exact shape scripts/diagnose.ps1 -Json prints on MAIN-PC.

    A local copy (not imported from diagnostics.tests) so a ui test never has
    to reach into another module's test internals (import-linter layering).
    """
    return {
        "schema": "argus-collector-diagnose/1",
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


def make_tk_root() -> tk.Tk:
    """`tk.Tk()` with a short retry.

    On Windows, creating a fresh Tcl interpreter immediately after a previous
    one in the same process was torn down occasionally races Tcl's library
    init (`TclError: invalid command name "tcl_findLibrary"` or a missing
    tk.tcl), even though the previous root called `destroy()` cleanly. A
    short retry is cheaper and more robust than serialising every GUI test.
    """
    last: tk.TclError | None = None
    for _attempt in range(TK_CREATE_RETRIES):
        try:
            return tk.Tk()
        except tk.TclError as exc:
            last = exc
            time.sleep(TK_CREATE_RETRY_DELAY_S)
    assert last is not None
    raise last
