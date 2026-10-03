"""check_no_cyrillic: no Cyrillic letters in code directories (CLAUDE.md rule 12).

PowerShell files must be pure ASCII on top of that: PowerShell 5.1 reads a
BOM-less file as ANSI, so any non-ASCII byte becomes garbage on MAIN-PC.
"""

from __future__ import annotations

import re
from pathlib import Path

from gates.common import GateResult, code_files, rel

CYRILLIC = re.compile("[" + chr(0x0400) + "-" + chr(0x04FF) + "]")
ALL_SUFFIXES = tuple(
    {
        ".py",
        ".ps1",
        ".html",
        ".css",
        ".js",
        ".mjs",
        ".yaml",
        ".yml",
        ".toml",
        ".json",
        ".md",
        ".txt",
        ".cfg",
        ".ini",
    }
)


def run(root: Path) -> GateResult:
    result = GateResult("no_cyrillic")
    for path in code_files(root, ALL_SUFFIXES):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            result.fail(f"{rel(path, root)}: not valid UTF-8")
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            if CYRILLIC.search(line):
                result.fail(f"{rel(path, root)}:{number}: Cyrillic text")
            elif path.suffix == ".ps1" and not line.isascii():
                result.fail(f"{rel(path, root)}:{number}: non-ASCII character in PowerShell")
    return result
