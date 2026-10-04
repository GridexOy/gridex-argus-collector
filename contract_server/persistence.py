"""Optional persistence of the stand: one JSON state file plus evidence blobs.

`StateFile` writes the whole state atomically (tmp file + `os.replace`).
`BlobStore` keeps the raw evidence bytes and the text used for quote checks;
with a directory (`<state_path>.evidence/`) they are files named by the
sha256 of the evidence_id, otherwise they live in memory only.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from contract_server.util import Json, sha256_hex


def _atomic_write(path: Path, data: bytes) -> None:
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


class StateFile:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> Json | None:
        if not self.path.is_file():
            return None
        data: Any = json.loads(self.path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None

    def save(self, state: Json) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write(self.path, json.dumps(state, ensure_ascii=False).encode("utf-8"))


class BlobStore:
    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory
        self._raw: dict[str, bytes] = {}
        self._text: dict[str, str] = {}
        if directory is not None:
            directory.mkdir(parents=True, exist_ok=True)

    def _file(self, key: str, suffix: str) -> Path | None:
        if self.directory is None:
            return None
        return self.directory / f"{sha256_hex(key.encode('utf-8'))}{suffix}"

    def put(self, key: str, raw: bytes, text: str) -> None:
        raw_file, text_file = self._file(key, ".bin"), self._file(key, ".txt")
        if raw_file is not None and text_file is not None:
            _atomic_write(raw_file, raw)
            _atomic_write(text_file, text.encode("utf-8"))
        self._raw[key] = raw
        self._text[key] = text

    def raw(self, key: str) -> bytes | None:
        if key not in self._raw:
            path = self._file(key, ".bin")
            if path is None or not path.is_file():
                return None
            self._raw[key] = path.read_bytes()
        return self._raw[key]

    def text(self, key: str) -> str | None:
        if key not in self._text:
            path = self._file(key, ".txt")
            if path is None or not path.is_file():
                return None
            self._text[key] = path.read_text(encoding="utf-8")
        return self._text[key]
