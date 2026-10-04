"""check_codegen: regenerating api_client from the OpenAPI contract is a no-op.

CLAUDE.md rule 14 ("one door"): the api_client client is generated, never
hand-edited. Reruns scripts/gen_api_client.py for real (it is deterministic)
and fails if that produces any change `git diff` can see, or a generated file
git does not track yet (the generator adds and removes chunk files). The
generator itself exits 1 when pyproject.toml's forbidden_modules list does
not match the generated modules.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from gates.common import GateResult, rel

GENERATOR = Path("scripts") / "gen_api_client.py"
GENERATED_DIR = Path("collector") / "src" / "argus_collector" / "api_client"
TIMEOUT_S = 60


def run(root: Path) -> GateResult:
    result = GateResult("gen_api_client")
    generator = root / GENERATOR
    if not generator.is_file():
        result.fail(f"{rel(generator, root)} missing")
        return result
    code, output = _run([sys.executable, str(generator)], root)
    if code != 0:
        result.fail(f"generator failed: {output[-2000:]}")
        return result
    gen_dir = GENERATED_DIR.as_posix()
    diff_code, diff_output = _run(["git", "diff", "--stat", "--", gen_dir], root)
    if diff_code != 0:
        result.fail(f"git diff failed: {diff_output}")
    elif diff_output.strip():
        result.fail(f"regenerating {gen_dir} is not a no-op:\n{diff_output.strip()}")
    # A new chunk file (types_<n>.py, serialization_<n>.py) is invisible to `git diff`;
    # only top-level files are generated (tests/ is hand-written).
    untracked = ["git", "ls-files", "--others", "--exclude-standard", gen_dir]
    new_code, new_output = _run(untracked, root)
    created = [line for line in new_output.splitlines() if "/" not in line[len(gen_dir) + 1 :]]
    if new_code != 0:
        result.fail(f"git ls-files failed: {new_output}")
    elif created:
        result.fail(f"regenerating {gen_dir} created untracked files: {', '.join(created)}")
    return result


def _run(args: list[str], root: Path) -> tuple[int, str]:
    try:
        done = subprocess.run(
            args,
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, f"cannot run {args[0]}: {exc}"
    return done.returncode, (done.stdout + done.stderr).strip()
