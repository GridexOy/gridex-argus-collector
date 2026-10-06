"""p95 (1 min) counts only the sends of the last minute (owner 06.10.2026, 0.4.8.6).

The panel showed `p95 (1 min): 89984.8 s`: events queued a day earlier and
acknowledged within the minute counted with their whole wait.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from argus_collector.delivery import contract as delivery
from argus_collector.storage import contract as storage


def _iso(seconds_ago: float) -> str:
    return (datetime.now(UTC) - timedelta(seconds=seconds_ago)).isoformat(
        timespec="milliseconds")


def _acked(conn: sqlite3.Connection, seq: int, created_ago: float, acked_ago: float) -> None:
    with conn:
        conn.execute(
            "INSERT INTO outbox (event_id, job_id, run_id, seq, type, event_json,"
            " evidence_ids_json, created_at, status, code, sent_at, acked_at)"
            " VALUES (?, 'j1', 'r1', ?, 'contact.observed', '{}', '[]', ?, 'accepted', '', ?, ?)",
            (f"e{seq}", seq, _iso(created_ago), _iso(acked_ago), _iso(acked_ago)),
        )


def test_an_event_queued_before_the_minute_is_not_counted(tmp_path: Path) -> None:
    conn = storage.connect(tmp_path / "c.sqlite3")
    try:
        _acked(conn, 1, created_ago=89_990, acked_ago=5)  # a day in the queue, sent now
        _acked(conn, 2, created_ago=12.0, acked_ago=10.0)  # queued and sent in the minute
        assert delivery.stats(conn).p95_s == 2.0
    finally:
        conn.close()


def test_only_old_events_give_no_p95(tmp_path: Path) -> None:
    conn = storage.connect(tmp_path / "c.sqlite3")
    try:
        _acked(conn, 1, created_ago=3_600, acked_ago=2)
        _acked(conn, 2, created_ago=100.0, acked_ago=90.0)  # acknowledged before the minute
        assert delivery.stats(conn).p95_s is None
    finally:
        conn.close()
