"""Runs whose request ARGUS refused as a whole (owner 06.10.2026: nothing leaves the
outbox but accepted / duplicate; a refusal of the request is no verdict on an event).

A 4xx on the request or a 409 lease keeps the run's events and snapshots pending: the
run waits a backoff and is asked again, the other runs go on meanwhile.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from argus_collector.delivery import service


@dataclass
class Holds:
    until: dict[str, float] = field(default_factory=dict)
    failures: dict[str, int] = field(default_factory=dict)
    kinds: dict[str, str] = field(default_factory=dict)

    def hold(self, run_id: str, kind: str, retry_after: str | None = None) -> None:
        count = self.failures.get(run_id, 0) + 1
        self.failures[run_id], self.kinds[run_id] = count, kind
        self.until[run_id] = time.monotonic() + service.backoff_s(count, retry_after)

    def held(self, run_id: str) -> bool:
        return self.until.get(run_id, 0.0) > time.monotonic()

    def release(self, run_id: str) -> None:
        for table in (self.until, self.failures, self.kinds):
            table.pop(run_id, None)

    def refused(self) -> bool:
        """A run waits because ARGUS refused its request (4xx): Lähetys shows an error."""
        return service.ERROR_PERMANENT in self.kinds.values()
