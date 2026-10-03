"""check_legacy: no code line copied from the old system (ASSETS section 19).

Each code line with ALL whitespace removed and length >= 40 is hashed with
sha256 and looked up in docs/legacy_line_hashes.txt. A single hit is a
warning (manual check), three or more consecutive hits fail the gate
(TZ_BLOCK0 section 12). Without the hash file the gate warns and passes.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from gates.common import GateResult, code_files, rel

HASH_FILE = Path("docs") / "legacy_line_hashes.txt"
MIN_LENGTH = 40
CONSECUTIVE_FAIL = 3
WHITESPACE = re.compile(r"\s+")


def line_hash(line: str) -> str | None:
    squeezed = WHITESPACE.sub("", line)
    if len(squeezed) < MIN_LENGTH:
        return None
    return hashlib.sha256(squeezed.encode("utf-8")).hexdigest()


def load_hashes(path: Path) -> set[str]:
    return {line.strip() for line in path.read_text(encoding="ascii").splitlines() if line.strip()}


def scan_file(path: Path, root: Path, hashes: set[str], result: GateResult) -> None:
    streak = 0
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        digest = line_hash(line)
        if digest is None:
            continue
        if digest in hashes:
            streak += 1
            result.warn(f"{rel(path, root)}:{number}: line hash found in legacy file")
            if streak == CONSECUTIVE_FAIL:
                result.fail(
                    f"{rel(path, root)}:{number}: {CONSECUTIVE_FAIL} consecutive legacy lines"
                )
        else:
            streak = 0


def run(root: Path) -> GateResult:
    result = GateResult("legacy")
    hash_path = root / HASH_FILE
    if not hash_path.is_file():
        result.warn(f"{HASH_FILE.as_posix()} missing, gate skipped")
        return result
    hashes = load_hashes(hash_path)
    for path in code_files(root):
        scan_file(path, root, hashes, result)
    return result
