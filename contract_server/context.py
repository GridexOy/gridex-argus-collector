"""`Stand` (state + clock + stores) and `Request`, shared by every handler."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from contract_server import openapi
from contract_server.errors import invalid
from contract_server.persistence import BlobStore, StateFile
from contract_server.registry import WorkerRegistry
from contract_server.schema import Schema
from contract_server.state import complete, empty_state
from contract_server.util import Json

DEFAULT_LEASE_SECONDS = 180.0
MAX_DETAIL_ERRORS = 5
Clock = Callable[[], datetime]


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass
class Stand:
    registry: WorkerRegistry
    clock: Clock = utc_now
    lease_seconds: float = DEFAULT_LEASE_SECONDS
    state_file: StateFile | None = None
    blobs: BlobStore = field(default_factory=BlobStore)
    state: Json = field(default_factory=empty_state)
    lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    @classmethod
    def create(
        cls,
        registry: WorkerRegistry,
        state_path: Path | None = None,
        clock: Clock | None = None,
        lease_seconds: float = DEFAULT_LEASE_SECONDS,
    ) -> Stand:
        """In memory without `state_path`; else load/save `state_path` + `<path>.evidence/`."""
        stand = cls(registry, clock or utc_now, float(lease_seconds))
        if state_path is not None:
            stand.state_file = StateFile(state_path)
            stand.blobs = BlobStore(state_path.with_name(state_path.name + ".evidence"))
            stand.state = complete(stand.state_file.load() or empty_state())
        return stand

    def now(self) -> float:
        return self.clock().timestamp()

    def save(self) -> None:
        if self.state_file is not None:
            self.state_file.save(self.state)


@dataclass
class Request:
    method: str
    path: str
    params: dict[str, str]
    headers: dict[str, str]
    body: bytes
    request_id: str
    principal: str = ""

    def header(self, name: str) -> str | None:
        return self.headers.get(name.lower())

    def json(self) -> Any:
        if not self.body:
            raise invalid("empty request body")
        try:
            return json.loads(self.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise invalid(f"malformed JSON body: {exc}") from exc

    def validated(self, schema: str | Schema) -> Json:
        """JSON body checked against an OpenAPI schema -> 400 invalid_input on mismatch."""
        return validated(self.json(), schema)


def validated(value: Any, schema: str | Schema) -> Json:
    errors = openapi.check(value, schema)
    if errors:
        raise invalid("; ".join(errors[:MAX_DETAIL_ERRORS]))
    result: Json = value
    return result
