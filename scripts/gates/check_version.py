"""check_version: VERSION is 0.<stage>.<step>.<fix> and pyproject agrees."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from gates.common import GateResult

VERSION_RE = re.compile(r"^0\.\d+\.\d+\.\d+$")


def read_version(root: Path) -> str:
    return (root / "VERSION").read_text(encoding="utf-8").strip()


def run(root: Path) -> GateResult:
    result = GateResult("version")
    path = root / "VERSION"
    if not path.is_file():
        result.fail("VERSION file missing")
        return result
    version = read_version(root)
    if not VERSION_RE.match(version):
        result.fail(f"VERSION {version!r} is not 0.<stage>.<step>.<fix>")
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        declared = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"].get("version")
        if declared != version:
            result.fail(f"pyproject.toml version {declared!r} differs from VERSION {version!r}")
    return result
