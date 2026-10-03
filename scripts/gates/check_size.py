"""check_size: file <= 200 lines, function <= 40 lines (CLAUDE.md rule 13).

Python functions are measured with `ast`; PowerShell functions from a line
starting with `function` to the next line that is a lone `}`.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from gates.common import GateResult, code_files, rel

MAX_FILE_LINES = 200
MAX_FUNCTION_LINES = 40
SIZED_SUFFIXES = (".py", ".ps1", ".html", ".css", ".js", ".mjs", ".yaml", ".yml", ".toml")
PS_FUNCTION = re.compile(r"^function\s+([\w-]+)")


def python_functions(text: str) -> list[tuple[str, int]]:
    tree = ast.parse(text)
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            end = node.end_lineno or node.lineno
            found.append((node.name, end - node.lineno + 1))
    return found


def powershell_functions(lines: list[str]) -> list[tuple[str, int]]:
    found: list[tuple[str, int]] = []
    name, start = "", 0
    for number, line in enumerate(lines, start=1):
        match = PS_FUNCTION.match(line)
        if match:
            name, start = match.group(1), number
        elif name and line.rstrip() == "}":
            found.append((name, number - start + 1))
            name = ""
    return found


def check_file(path: Path, root: Path, result: GateResult) -> None:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if len(lines) > MAX_FILE_LINES:
        result.fail(f"{rel(path, root)}: {len(lines)} lines > {MAX_FILE_LINES}")
    functions: list[tuple[str, int]] = []
    if path.suffix == ".py":
        try:
            functions = python_functions(text)
        except SyntaxError as exc:
            result.fail(f"{rel(path, root)}: syntax error: {exc}")
    elif path.suffix == ".ps1":
        functions = powershell_functions(lines)
    for name, length in functions:
        if length > MAX_FUNCTION_LINES:
            result.fail(
                f"{rel(path, root)}: function {name} is {length} lines > {MAX_FUNCTION_LINES}"
            )


def run(root: Path) -> GateResult:
    result = GateResult("size")
    for path in code_files(root, SIZED_SUFFIXES):
        check_file(path, root, result)
    return result
