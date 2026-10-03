"""The gates catch what they are for: run them on synthetic trees."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

from gates import (  # noqa: E402
    check_i18n,
    check_legacy,
    check_no_cyrillic,
    check_size,
    check_version,
)
from gates.common import repo_root  # noqa: E402


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_repo_root_is_the_tree_with_version() -> None:
    assert repo_root() == ROOT and (ROOT / "VERSION").is_file()


CYRILLIC_WORD = "".join(chr(c) for c in (0x43F, 0x440, 0x438, 0x432, 0x435, 0x442))


def test_cyrillic_is_caught_in_code_but_not_in_docs(tmp_path: Path) -> None:
    write(tmp_path / "scripts" / "x.py", f"name = {CYRILLIC_WORD!r}\n")
    write(tmp_path / "docs" / "x.md", CYRILLIC_WORD + "\n")
    result = check_no_cyrillic.run(tmp_path)
    assert not result.ok and result.errors == ["scripts/x.py:1: Cyrillic text"]


def test_size_limits_for_python_and_powershell(tmp_path: Path) -> None:
    long_function = "def f():\n" + "    x = 1\n" * 41
    write(tmp_path / "collector" / "a.py", long_function)
    write(tmp_path / "scripts" / "b.ps1", "function Foo {\n" + "  $x = 1\n" * 40 + "}\n")
    write(tmp_path / "scripts" / "c.py", "x = 1\n" * 201)
    errors = check_size.run(tmp_path).errors
    assert any("function f is 42 lines" in e for e in errors)
    assert any("function Foo is 42 lines" in e for e in errors)
    assert any("c.py: 201 lines" in e for e in errors)


@pytest.mark.parametrize(("text", "ok"), [("0.0.1.0\n", True), ("1.0.0\n", False)])
def test_version_shape(tmp_path: Path, text: str, ok: bool) -> None:
    write(tmp_path / "VERSION", text)
    assert check_version.run(tmp_path).ok is ok


def test_version_must_match_pyproject(tmp_path: Path) -> None:
    write(tmp_path / "VERSION", "0.0.1.0\n")
    write(tmp_path / "pyproject.toml", '[project]\nname = "x"\nversion = "0.0.2.0"\n')
    assert not check_version.run(tmp_path).ok


def test_legacy_warns_on_one_hit_and_fails_on_three(tmp_path: Path) -> None:
    lines = [f"this_is_a_copied_line_number_{i}_with_enough_length_to_count()" for i in range(3)]
    hashes = [check_legacy.line_hash(line) for line in lines]
    write(tmp_path / "docs" / "legacy_line_hashes.txt", "\n".join(h for h in hashes if h) + "\n")
    write(tmp_path / "collector" / "one.py", lines[0] + "\nshort = 1\n")
    result = check_legacy.run(tmp_path)
    assert result.ok and len(result.warnings) == 1
    write(tmp_path / "collector" / "three.py", "\n".join(lines) + "\n")
    result = check_legacy.run(tmp_path)
    assert not result.ok and any("3 consecutive" in e for e in result.errors)


def test_legacy_without_hash_file_is_a_warning(tmp_path: Path) -> None:
    result = check_legacy.run(tmp_path)
    assert result.ok and "missing" in result.warnings[0]


def test_i18n_unknown_and_unused_keys(tmp_path: Path) -> None:
    catalogue = json.dumps({"a.used": "x", "a.unused": "y"})
    write(tmp_path / "collector" / "messages" / "fi.json", catalogue)
    write(tmp_path / "collector" / "src" / "m.py", 'k = "a.used"\nz = "a.missing"\n')
    write(tmp_path / "scripts" / "d.ps1", "Get-Msg 'a.fromps'\n")
    errors = check_i18n.run(tmp_path).errors
    assert any("'a.missing' used in collector/src/m.py:2" in e for e in errors)
    assert any("'a.fromps' used in scripts/d.ps1:1" in e for e in errors)
    assert any("'a.unused' in collector/messages/fi.json is used nowhere" in e for e in errors)
    assert not any("a.used" in e for e in errors)
