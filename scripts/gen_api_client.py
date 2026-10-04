"""Generate the `api_client` module from docs/ARGUS20_COLLECTOR_OPENAPI.json.

Usage: python scripts/gen_api_client.py
Regenerating must be a no-op (CLAUDE.md rule 14, "one door"):
`scripts/gates/check_codegen.py` reruns this and checks `git diff` over
`collector/src/argus_collector/api_client/` is empty. The manifest of
covered operationIds lives in `scripts/codegen/manifest.py` (today:
heartbeat only -- ARGUS20_TZ_TANDEM.md pair A1).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from codegen.manifest import MANIFEST, SPEC_RELATIVE_PATH  # noqa: E402
from codegen.model import build_model  # noqa: E402
from codegen.render_contract import render_contract  # noqa: E402
from codegen.render_readme import render_readme  # noqa: E402
from codegen.render_repository import render_repository  # noqa: E402
from codegen.render_serialization import render_serialization  # noqa: E402
from codegen.render_service import render_service  # noqa: E402
from codegen.spec import load_spec  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
TARGET_DIR = REPO_ROOT / "collector" / "src" / "argus_collector" / "api_client"


def write_if_changed(path: Path, content: str) -> bool:
    before = path.read_text(encoding="utf-8") if path.is_file() else None
    if before == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)
    return True


def main(argv: list[str] | None = None) -> int:
    if argv:
        print("gen_api_client.py takes no arguments", file=sys.stderr)
        return 2
    spec_path = REPO_ROOT / SPEC_RELATIVE_PATH
    spec = load_spec(spec_path)
    model = build_model(spec, MANIFEST)
    source_rel = SPEC_RELATIVE_PATH.as_posix()
    outputs = {
        TARGET_DIR / "service.py": render_service(model, source_rel),
        TARGET_DIR / "repository.py": render_repository(model, source_rel),
        TARGET_DIR / "contract.py": render_contract(model, source_rel),
        TARGET_DIR / "README.md": render_readme(model, source_rel),
    }
    for name, content in render_serialization(model, source_rel).items():
        outputs[TARGET_DIR / name] = content
    changed = [path for path, content in outputs.items() if write_if_changed(path, content)]
    for path in changed:
        print(f"generated: {path.relative_to(REPO_ROOT).as_posix()}")
    if not changed:
        print("api_client is already up to date")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
