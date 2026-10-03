"""check_docs: every module has README (<= 40 lines), contract/service/repository,
tests/; a row in ARGUS20_COLLECTOR_MODULES.md; the changelog has the current VERSION."""

from __future__ import annotations

from pathlib import Path

from gates.check_version import read_version
from gates.common import GateResult, rel

PACKAGE = Path("collector") / "src" / "argus_collector"
MODULES_DOC = Path("docs") / "ARGUS20_COLLECTOR_MODULES.md"
CHANGELOG = Path("docs") / "ARGUS20_COLLECTOR_CHANGELOG.md"
REQUIRED_FILES = ("contract.py", "service.py", "repository.py")
MAX_README_LINES = 40
EXTRA_DIRS = ("test_site", "contract_server")


def module_dirs(root: Path) -> list[Path]:
    base = root / PACKAGE
    if not base.is_dir():
        return []
    return sorted(p for p in base.iterdir() if p.is_dir() and p.name != "__pycache__")


def check_module(path: Path, root: Path, registry: str, result: GateResult) -> None:
    name = rel(path, root)
    readme = path / "README.md"
    if not readme.is_file():
        result.fail(f"{name}: README.md missing")
    else:
        lines = len(readme.read_text(encoding="utf-8").splitlines())
        if lines > MAX_README_LINES:
            result.fail(f"{name}: README.md has {lines} lines > {MAX_README_LINES}")
    for required in REQUIRED_FILES:
        if not (path / required).is_file():
            result.fail(f"{name}: {required} missing")
    if not (path / "tests").is_dir():
        result.fail(f"{name}: tests/ missing")
    if f"`{path.name}`" not in registry:
        result.fail(f"{name}: no row in {MODULES_DOC.as_posix()}")


def run(root: Path) -> GateResult:
    result = GateResult("docs")
    registry_path = root / MODULES_DOC
    if not registry_path.is_file():
        result.fail(f"{MODULES_DOC.as_posix()} missing")
        return result
    registry = registry_path.read_text(encoding="utf-8")
    for path in module_dirs(root):
        check_module(path, root, registry, result)
    for extra in EXTRA_DIRS:
        if (root / extra).is_dir() and not (root / extra / "README.md").is_file():
            result.fail(f"{extra}/README.md missing")
    changelog = root / CHANGELOG
    version = read_version(root)
    if not changelog.is_file():
        result.fail(f"{CHANGELOG.as_posix()} missing")
    elif f"## {version}" not in changelog.read_text(encoding="utf-8"):
        result.fail(f"{CHANGELOG.as_posix()}: no entry '## {version}'")
    return result
