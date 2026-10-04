"""In-memory worker registry for the heartbeat test double.

Not the real ARGUS auth: a plain `{token: worker_id}` dict, seeded at
startup, with no persistence across restarts and no hashing. The real
server's token hashing and revocation live in the other team's pair B1.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime

DEFAULT_TOKENS: dict[str, str] = {"test-token-abc": "worker-main-pc"}


@dataclass
class WorkerRegistry:
    tokens: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_TOKENS))
    last_seen_at: dict[str, datetime] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def resolve(self, token: str | None) -> str | None:
        """Known token -> worker_id; missing or unknown token -> None."""
        if not token:
            return None
        return self.tokens.get(token)

    def record_heartbeat(self, worker_id: str, when: datetime) -> None:
        with self._lock:
            self.last_seen_at[worker_id] = when

    def seen_at(self, worker_id: str) -> datetime | None:
        with self._lock:
            return self.last_seen_at.get(worker_id)
