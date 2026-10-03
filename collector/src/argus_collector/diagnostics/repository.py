"""Probes that touch the machine: diagnose.ps1 on Windows, Python elsewhere.

The Python probes exist so the panel and the tests work on Linux/macOS;
on Windows the single source of truth is `scripts/diagnose.ps1 -Json`.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

from argus_collector.diagnostics.service import Facts

CHROME_CANDIDATES = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser")
PROBE_TIMEOUT_S = 5
MODEL_TIMEOUT_S = 1.5
POWERSHELL_TIMEOUT_S = 60


class DiagnosticsError(RuntimeError):
    """diagnose.ps1 could not be run or returned garbage."""


def run_powershell_diagnose(script: Path, model_endpoint: str) -> str:
    """Run diagnose.ps1 -Json and return its stdout (Windows only)."""
    cmd = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script),
        "-Json",
        "-ModelEndpoint",
        model_endpoint,
    ]
    try:
        done = subprocess.run(
            cmd, capture_output=True, text=True, timeout=POWERSHELL_TIMEOUT_S, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DiagnosticsError(f"cannot run {script.name}: {exc}") from exc
    if done.returncode != 0:
        raise DiagnosticsError(f"{script.name} exit {done.returncode}: {done.stderr.strip()}")
    return done.stdout


def _run(cmd: list[str]) -> str:
    done = subprocess.run(cmd, capture_output=True, text=True, timeout=PROBE_TIMEOUT_S, check=False)
    return done.stdout.strip() if done.returncode == 0 else ""


def probe_chrome() -> tuple[str, str]:
    for name in CHROME_CANDIDATES:
        path = shutil.which(name)
        if path:
            return path, _run([path, "--version"])
    return "", ""


def probe_gpu() -> tuple[str, str, int, int, str]:
    """(name, driver, memory_total_mb, memory_used_mb, source)."""
    smi = shutil.which("nvidia-smi")
    if not smi:
        return "", "", 0, 0, "none"
    query = "--query-gpu=name,driver_version,memory.total,memory.used"
    out = _run([smi, query, "--format=csv,noheader,nounits"])
    if not out:
        return "", "", 0, 0, "none"
    parts = [p.strip() for p in out.splitlines()[0].split(",")]
    if len(parts) < 4:
        return "", "", 0, 0, "none"
    return parts[0], parts[1], int(float(parts[2])), int(float(parts[3])), "nvidia-smi"


def probe_memory() -> tuple[int, int]:
    """(total_mb, free_mb) from /proc/meminfo, else sysconf."""
    meminfo = Path("/proc/meminfo")
    if meminfo.is_file():
        values: dict[str, int] = {}
        for line in meminfo.read_text(encoding="ascii").splitlines():
            key, _, rest = line.partition(":")
            values[key] = int(rest.split()[0]) if rest.split() else 0
        return values.get("MemTotal", 0) // 1024, values.get("MemAvailable", 0) // 1024
    if hasattr(os, "sysconf"):
        page = os.sysconf("SC_PAGE_SIZE")
        return os.sysconf("SC_PHYS_PAGES") * page // (1024 * 1024), 0
    return windows_memory()


def windows_memory() -> tuple[int, int]:
    """(total_mb, free_mb) via GlobalMemoryStatusEx; used only by tests on Windows."""
    import ctypes

    class MemoryStatus(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_uint32),
            ("dwMemoryLoad", ctypes.c_uint32),
            ("ullTotalPhys", ctypes.c_uint64),
            ("ullAvailPhys", ctypes.c_uint64),
            ("ullTotalPageFile", ctypes.c_uint64),
            ("ullAvailPageFile", ctypes.c_uint64),
            ("ullTotalVirtual", ctypes.c_uint64),
            ("ullAvailVirtual", ctypes.c_uint64),
            ("ullAvailExtendedVirtual", ctypes.c_uint64),
        ]

    status = MemoryStatus()
    status.dwLength = ctypes.sizeof(MemoryStatus)
    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    if not kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return 0, 0
    mib = 1024 * 1024
    return int(status.ullTotalPhys) // mib, int(status.ullAvailPhys) // mib


def probe_disk(path: Path) -> tuple[str, float, float]:
    usage = shutil.disk_usage(path)
    gib = 1024**3
    return str(path), round(usage.total / gib, 1), round(usage.free / gib, 1)


def probe_model(endpoint: str) -> tuple[bool, str]:
    url = endpoint.rstrip("/") + "/health"
    try:
        with urllib.request.urlopen(url, timeout=MODEL_TIMEOUT_S) as resp:
            return resp.status < 500, f"HTTP {resp.status}"
    except urllib.error.HTTPError as exc:
        return exc.code < 500, f"HTTP {exc.code}"
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return False, f"no answer: {exc}"


def python_facts(model_endpoint: str, disk_path: Path) -> Facts:
    chrome_path, chrome_version = probe_chrome()
    gpu_name, gpu_driver, gpu_total, gpu_used, gpu_source = probe_gpu()
    mem_total, mem_free = probe_memory()
    disk, disk_total, disk_free = probe_disk(disk_path)
    reachable, detail = probe_model(model_endpoint)
    return Facts(
        os_name=f"{platform.system()} {platform.release()}".strip(),
        os_version=platform.version(),
        chrome_path=chrome_path,
        chrome_version=chrome_version,
        gpu_name=gpu_name,
        gpu_driver=gpu_driver,
        gpu_memory_total_mb=gpu_total,
        gpu_memory_used_mb=gpu_used,
        gpu_source=gpu_source,
        memory_total_mb=mem_total,
        memory_free_mb=mem_free,
        disk_path=disk,
        disk_total_gb=disk_total,
        disk_free_gb=disk_free,
        model_endpoint=model_endpoint,
        model_reachable=reachable,
        model_detail=detail,
    )
