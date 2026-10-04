"""Generate the `api_client` module from docs/ARGUS20_COLLECTOR_OPENAPI.json.

Usage: python scripts/gen_api_client.py
Regenerating must be a no-op (CLAUDE.md rule 14, "one door"):
`scripts/gates/check_codegen.py` reruns this and checks `git diff` over
`collector/src/argus_collector/api_client/` is empty. The manifest of
covered operationIds lives in `scripts/codegen/manifest.py`. Every top-level
file of api_client/ except `__init__.py` is generated: a stale one (a chunk
that no longer exists) is removed. Exit 1 when pyproject.toml's
import-linter forbidden_modules does not list exactly the generated modules.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from codegen.layout import render_all  # noqa: E402
from codegen.manifest import MANIFEST, SPEC_RELATIVE_PATH  # noqa: E402
from codegen.model import build_model  # noqa: E402
from codegen.pyproject_check import forbidden_mismatch  # noqa: E402
from codegen.spec import load_spec  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
TARGET_DIR = REPO_ROOT / "collector" / "src" / "argus_collector" / "api_client"
KEPT = {"__init__.py"}
GENERATED_SUFFIXES = (".py", ".md")


def write_if_changed(path: Path, content: str) -> bool:
    before = path.read_text(encoding="utf-8") if path.is_file() else None
    if before == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)
    return True


def remove_stale(outputs: dict[str, str]) -> list[Path]:
    stale = [
        path
        for path in sorted(TARGET_DIR.iterdir())
        if path.is_file()
        and path.suffix in GENERATED_SUFFIXES
        and path.name not in KEPT
        and path.name not in outputs
    ]
    for path in stale:
        path.unlink()
    return stale


def main(argv: list[str] | None = None) -> int:
    if argv:
        print("gen_api_client.py takes no arguments", file=sys.stderr)
        return 2
    spec = load_spec(REPO_ROOT / SPEC_RELATIVE_PATH)
    outputs = render_all(build_model(spec, MANIFEST), SPEC_RELATIVE_PATH.as_posix())
    changed = [name for name, text in outputs.items() if write_if_changed(TARGET_DIR / name, text)]
    for name in changed:
        print(f"generated: {(TARGET_DIR / name).relative_to(REPO_ROOT).as_posix()}")
    for path in remove_stale(outputs):
        changed.append(path.name)
        print(f"removed: {path.relative_to(REPO_ROOT).as_posix()}")
    if not changed:
        print("api_client is already up to date")
    modules = [name[: -len(".py")] for name in outputs if name.endswith(".py")]
    missing, extra = forbidden_mismatch(REPO_ROOT / "pyproject.toml", modules)
    for module in missing:
        print(f"pyproject.toml: add {module!r} to import-linter forbidden_modules", file=sys.stderr)
    for module in extra:
        print(f"pyproject.toml: drop {module!r} from forbidden_modules", file=sys.stderr)
    return 1 if missing or extra else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
