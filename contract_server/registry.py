"""In-memory token registry of the contract server (test stand only).

Not the real ARGUS auth: plain `{token: worker_id}` worker tokens and a set
of system tokens, seeded at startup, no hashing. Revocation is in memory
too (`revoke(worker_id)`); the real server's token hashing and revocation
live in the other team's pair B1.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime

DEFAULT_TOKENS: dict[str, str] = {"test-token-abc": "worker-main-pc"}
DEFAULT_SYSTEM_TOKENS: frozenset[str] = frozenset({"system-token-xyz"})


@dataclass
class WorkerRegistry:
    tokens: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_TOKENS))
    system_tokens: set[str] = field(default_factory=lambda: set(DEFAULT_SYSTEM_TOKENS))
    revoked: set[str] = field(default_factory=set)
    last_seen_at: dict[str, datetime] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def resolve(self, token: str | None) -> str | None:
        """Known worker token -> worker_id; missing or unknown token -> None."""
        if not token:
            return None
        return self.tokens.get(token)

    def is_system(self, token: str | None) -> bool:
        return bool(token) and token in self.system_tokens

    def revoke(self, worker_id: str) -> None:
        """Every token of this worker now gets 403 worker_revoked."""
        with self._lock:
            self.revoked.add(worker_id)

    def is_revoked(self, worker_id: str) -> bool:
        with self._lock:
            return worker_id in self.revoked

    def known_worker(self, worker_id: str) -> bool:
        return worker_id in self.tokens.values()

    def record_heartbeat(self, worker_id: str, when: datetime) -> None:
        with self._lock:
            self.last_seen_at[worker_id] = when

    def seen_at(self, worker_id: str) -> datetime | None:
        with self._lock:
            return self.last_seen_at.get(worker_id)
