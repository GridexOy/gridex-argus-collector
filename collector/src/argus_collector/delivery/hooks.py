"""Shared shapes of delivery: where to send, what the scheduler answers."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Protocol

from argus_collector.api_client import contract as api


@dataclass(frozen=True)
class ApiTarget:
    base_url: str  # ARGUS address + /api/collector
    worker_id: str
    token: str
    proxy_mode: str  # system | direct


class DeliveryHooks(Protocol):
    """What delivery needs from the scheduler (job tokens live in its tables)."""

    def token_for(self, conn: sqlite3.Connection, job_id: str, run_id: str) -> str | None: ...
    def lease_problem(self, job_id: str, run_id: str, code: str, token: str) -> None: ...
    def rejected(self, conn: sqlite3.Connection, job_id: str, kind: str, code: str) -> None: ...
    def applied(self, conn: sqlite3.Connection, job_id: str, resp: api.EventsResponse) -> None: ...


class Failed(Exception):
    def __init__(self, error: str, retry_after: str | None = None) -> None:
        super().__init__(error)
        self.error = error
        self.retry_after = retry_after
