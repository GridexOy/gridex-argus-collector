"""Tool gates: ruff, mypy --strict, import-linter, pip-audit (TZ_SELAIN section 12.3).

Each runs the tool from the current interpreter's environment so the same
venv is used on Windows and in CI. A missing tool is a failure, not a skip.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from gates.common import GateResult

TIMEOUT_S = 600
PYTHON_TARGETS = ("collector", "contract_server", "test_site", "scripts")
SOURCE_DIR = Path("collector") / "src"


def _run_python(
    name: str, python_args: list[str], root: Path, env: dict[str, str] | None = None
) -> tuple[int, str]:
    """Run `sys.executable <python_args>` (the caller includes `-m`/`-c` itself)."""
    try:
        done = subprocess.run(
            [sys.executable, *python_args],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TIMEOUT_S,
            check=False,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, f"{name}: cannot run: {exc}"
    output = (done.stdout + done.stderr).strip()
    if done.returncode != 0 and "No module named" in output:
        return 127, f"{name}: not installed in this environment ({output.splitlines()[-1]})"
    return done.returncode, output


def _run(
    name: str, module_args: list[str], root: Path, env: dict[str, str] | None = None
) -> tuple[int, str]:
    return _run_python(name, ["-m", *module_args], root, env)


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


IMPORT_LINTER_SNIPPET = "from importlinter.cli import lint_imports_command; lint_imports_command()"


def run_import_linter(root: Path) -> GateResult:
    """Two fixes this gate needs to mean anything (both found while adding api_client):

    1. `importlinter` has no `__main__.py`, so `python -m importlinter.cli
       lint_imports` (the previous invocation) silently imports the module,
       does nothing with the "lint_imports" argument and exits 0 -- it never
       actually ran a single check. The console script (`lint-imports.exe`)
       calls `importlinter.cli.lint_imports_command()`; running that same
       call through `python -c` is the real equivalent.
    2. `argus_collector` otherwise resolves through whatever the venv's
       site-packages .pth already points at (the last `install.ps1`'s
       `%LOCALAPPDATA%\\...\\app` copy), which lags behind this checkout --
       a brand-new module (like `api_client`) is invisible there until
       installed. Prepending collector/src to PYTHONPATH makes this checkout
       win, the same way pytest's own `pythonpath` setting already does.
    """
    result = GateResult("import_linter")
    env = dict(os.environ)
    source = str(root / SOURCE_DIR)
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = source if not existing else source + os.pathsep + existing
    code, output = _run_python("import-linter", ["-c", IMPORT_LINTER_SNIPPET], root, env)
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
