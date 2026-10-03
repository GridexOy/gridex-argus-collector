"""Tool gates: ruff, mypy --strict, import-linter, pip-audit (TZ_SELAIN section 12.3).

Each runs the tool from the current interpreter's environment so the same
venv is used on Windows and in CI. A missing tool is a failure, not a skip.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from gates.common import GateResult

TIMEOUT_S = 600
PYTHON_TARGETS = ("collector", "test_site", "scripts")


def _run(name: str, args: list[str], root: Path) -> tuple[int, str]:
    try:
        done = subprocess.run(
            [sys.executable, "-m", *args],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, f"{name}: cannot run: {exc}"
    output = (done.stdout + done.stderr).strip()
    if done.returncode != 0 and "No module named" in output:
        return 127, f"{name}: not installed in this environment ({output.splitlines()[-1]})"
    return done.returncode, output


def _tail(output: str, limit: int = 15) -> list[str]:
    lines = output.splitlines()
    return lines[-limit:] if len(lines) > limit else lines


def run_ruff(root: Path) -> GateResult:
    result = GateResult("ruff")
    code, output = _run("ruff", ["ruff", "check", *PYTHON_TARGETS], root)
    if code != 0:
        for line in _tail(output):
            result.fail(line)
    return result


def run_mypy(root: Path) -> GateResult:
    result = GateResult("mypy")
    code, output = _run("mypy", ["mypy", "--strict"], root)
    if code != 0:
        for line in _tail(output):
            result.fail(line)
    return result


def run_import_linter(root: Path) -> GateResult:
    result = GateResult("import_linter")
    code, output = _run("import-linter", ["importlinter.cli", "lint_imports"], root)
    if code != 0:
        for line in _tail(output):
            result.fail(line)
    return result


def run_pip_audit(root: Path) -> GateResult:
    """Vulnerabilities fail; a network failure is a warning so offline runs stay honest."""
    result = GateResult("pip_audit")
    args = [
        "pip_audit",
        "--progress-spinner",
        "off",
        "-r",
        "requirements.txt",
        "-r",
        "requirements-dev.txt",
    ]
    code, output = _run("pip-audit", args, root)
    if code == 0:
        return result
    if code == 127 or "No module named" in output:
        result.fail(output)
    elif "Found" in output and "vulnerab" in output:
        for line in _tail(output):
            result.fail(line)
    else:
        result.warn("pip-audit could not complete (network?): " + " | ".join(_tail(output, 3)))
    return result
