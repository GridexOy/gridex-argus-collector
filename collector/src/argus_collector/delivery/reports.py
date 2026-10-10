"""What a finished run sent and what ARGUS answered - for the reports (`pilot`)."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass

from argus_collector.delivery import repository as repo


@dataclass(frozen=True)
class SentEvent:
    """One outbox event of a run with what ARGUS answered (for reports)."""

    type: str
    payload: dict[str, object]
    status: str  # pending | accepted | duplicate | rejected
    channel_status: str | None  # the strongest K3 status ARGUS gave a contact event


def run_events(conn: sqlite3.Connection, run_id: str, event_type: str) -> list[dict[str, object]]:
    """Payloads of the run's events of one type (e.g. model.called for job.finished)."""
    out: list[dict[str, object]] = []
    for row in repo.run_rows(conn, run_id):
        if row["type"] == event_type:
            payload = json.loads(row["event_json"]).get("payload", {})
            out.append(payload if isinstance(payload, dict) else {})
    return out


def run_results(conn: sqlite3.Connection, run_id: str) -> list[SentEvent]:
    out = []
    for row in repo.run_rows(conn, run_id):
        payload = json.loads(row["event_json"]).get("payload", {})
        out.append(SentEvent(str(row["type"]), payload if isinstance(payload, dict) else {},
                             str(row["status"]), row["channel_status"]))
    return out
