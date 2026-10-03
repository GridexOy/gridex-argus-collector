"""Shared pieces of the gates: repo root, code directories, result type."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

CODE_DIRS = ("collector", "contract_server", "test_site", "scripts")
CODE_FILES = ("config.example.yaml", "pyproject.toml")
CODE_SUFFIXES = (".py", ".ps1", ".html", ".css", ".js", ".mjs", ".yaml", ".yml", ".toml", ".json")
SKIP_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "node_modules",
}


@dataclass
class GateResult:
    name: str
    ok: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def fail(self, message: str) -> None:
        self.ok = False
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def code_files(root: Path, suffixes: tuple[str, ...] = CODE_SUFFIXES) -> Iterator[Path]:
    """Every code file under the code directories plus the root code files."""
    for name in CODE_DIRS:
        base = root / name
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file() and path.suffix in suffixes and not _skipped(path, root):
                yield path
    for name in CODE_FILES:
        path = root / name
        if path.is_file() and path.suffix in suffixes:
            yield path


def _skipped(path: Path, root: Path) -> bool:
    return any(part in SKIP_DIRS for part in path.relative_to(root).parts)


def rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()
