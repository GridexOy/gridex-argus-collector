"""Storage access of the ui module: the Finnish message catalogue."""

from __future__ import annotations

import json
from pathlib import Path

from argus_collector.runtime import contract as runtime

MESSAGES_FILE = Path("collector") / "messages" / "fi.json"


class Messages:
    """`t(key, **params)` over `collector/messages/fi.json`; missing keys raise."""

    def __init__(self, catalogue: dict[str, str]) -> None:
        self._catalogue = catalogue

    def t(self, key: str, **params: object) -> str:
        template = self._catalogue[key]
        return template.format(**params) if params else template

    def keys(self) -> set[str]:
        return set(self._catalogue)


def messages_path() -> Path:
    return runtime.repo_root() / MESSAGES_FILE


def load_messages(path: Path | None = None) -> Messages:
    raw = json.loads((path or messages_path()).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not all(isinstance(v, str) for v in raw.values()):
        raise ValueError(f"{path or messages_path()}: expected an object of strings")
    return Messages({str(k): str(v) for k, v in raw.items()})
