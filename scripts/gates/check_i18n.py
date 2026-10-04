"""check_i18n: every key used in code exists in fi.json and every key is used.

A used key is a string literal in collector/src (outside tests) whose first
segment is a namespace of fi.json (`resources.`, `browser.`, ...), or the
argument of `Get-Msg '<key>'` in scripts/*.ps1. The generated `api_client`
is not scanned: its literals are wire values of the contract (event types
such as `job.finished`), never panel strings, and they share the `job.`
namespace with the keys `job.state.*` of TZ_SELAIN 6.1.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

from gates.common import GateResult, rel

MESSAGES = Path("collector") / "messages" / "fi.json"
SOURCE = Path("collector") / "src"
SCRIPTS = Path("scripts")
NOT_UI = ("tests", "api_client")
KEY_RE = re.compile(r"^[a-z][A-Za-z0-9_]*(\.[A-Za-z0-9_]+)+$")
PS_KEY_RE = re.compile(r"Get-Msg\s+'([A-Za-z0-9_.]+)'")


def load_keys(path: Path) -> set[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected an object")
    return {str(k) for k in data}


def python_literals(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if KEY_RE.match(node.value):
                found.append((node.lineno, node.value))
    return found


def used_keys(root: Path, namespaces: set[str]) -> dict[str, list[str]]:
    """key -> places, from Python literals in matching namespaces and Get-Msg calls."""
    used: dict[str, list[str]] = {}
    for path in sorted((root / SOURCE).rglob("*.py")):
        if any(part in NOT_UI for part in path.relative_to(root).parts):
            continue
        for line, value in python_literals(path):
            if value.split(".", 1)[0] in namespaces:
                used.setdefault(value, []).append(f"{rel(path, root)}:{line}")
    for path in sorted((root / SCRIPTS).glob("*.ps1")):
        for line, text in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            for match in PS_KEY_RE.finditer(text):
                used.setdefault(match.group(1), []).append(f"{rel(path, root)}:{line}")
    return used


def run(root: Path) -> GateResult:
    result = GateResult("i18n")
    path = root / MESSAGES
    if not path.is_file():
        result.fail(f"{MESSAGES.as_posix()} missing")
        return result
    keys = load_keys(path)
    namespaces = {key.split(".", 1)[0] for key in keys}
    used = used_keys(root, namespaces)
    for key, places in sorted(used.items()):
        if key not in keys:
            result.fail(f"key {key!r} used in {places[0]} is not in {MESSAGES.as_posix()}")
    for key in sorted(keys - set(used)):
        result.fail(f"key {key!r} in {MESSAGES.as_posix()} is used nowhere")
    return result
