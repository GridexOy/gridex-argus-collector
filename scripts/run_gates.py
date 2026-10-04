"""Run the gates of TZ_SELAIN section 12.3: python scripts/run_gates.py [--only a b].

Exit 0 when every gate is green (warnings allowed), 1 when any gate is red.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gates import (  # noqa: E402 - path set above
    check_codegen,
    check_docs,
    check_i18n,
    check_legacy,
    check_no_cyrillic,
    check_size,
    check_tools,
    check_version,
)
from gates.common import GateResult, repo_root  # noqa: E402

GATES: dict[str, Callable[[Path], GateResult]] = {
    "version": check_version.run,
    "no_cyrillic": check_no_cyrillic.run,
    "size": check_size.run,
    "docs": check_docs.run,
    "i18n": check_i18n.run,
    "legacy": check_legacy.run,
    "ruff": check_tools.run_ruff,
    "mypy": check_tools.run_mypy,
    "import_linter": check_tools.run_import_linter,
    "pip_audit": check_tools.run_pip_audit,
    "gen_api_client": check_codegen.run,
}
MAX_WARNINGS_SHOWN = 10


def print_result(result: GateResult) -> None:
    state = "ok" if result.ok else "FAIL"
    if result.ok and result.warnings:
        state = "ok (warnings)"
    print(f"{result.name:<14} {state}")
    for line in result.errors:
        print(f"    error: {line}")
    for line in result.warnings[:MAX_WARNINGS_SHOWN]:
        print(f"    warning: {line}")
    hidden = len(result.warnings) - MAX_WARNINGS_SHOWN
    if hidden > 0:
        print(f"    ... {hidden} more warnings")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ARGUS collector gates")
    parser.add_argument("--only", nargs="+", choices=sorted(GATES), default=None)
    args = parser.parse_args(argv)
    root = repo_root()
    names = args.only or list(GATES)
    failed = 0
    for name in names:
        result = GATES[name](root)
        print_result(result)
        failed += 0 if result.ok else 1
    print(f"gates: {len(names) - failed} ok, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
