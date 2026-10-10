"""The queue of an earlier version is terminal: `Vanhentunut` (owner 10.10.2026).

On MAIN-PC 408 events and 343 refusals of the 05-06.10 runs sat in the outbox for
days: their leases were long gone, so nothing could ever acknowledge them, and the
panel kept counting them as waiting and as errors. Migration 5 gives every such row
the terminal status `expired`; it is never sent again, counts neither as waiting nor
as an error, and the panel says how many there are.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from argus_collector.delivery import contract as delivery
from argus_collector.delivery import repository as repo
from argus_collector.storage import contract as storage

ROW = ("event", "job-1", "run-1", 1, "contact.observed")


def _old_rows(conn: sqlite3.Connection) -> None:
    """Rows as an earlier version left them, with migration 5 not yet applied."""
    conn.execute("DELETE FROM schema_version WHERE version = 5")
    body = json.dumps({"seq": 1})
    for n, status in ((1, "pending"), (2, "waiting"), (3, "rejected"), (4, "accepted")):
        conn.execute(
            "INSERT INTO outbox (event_id, job_id, run_id, seq, type, event_json,"
            " evidence_ids_json, created_at, status) VALUES (?, ?, ?, ?, ?, ?, '[]', ?, ?)",
            (f"e{n}", "job-1", "run-1", n, "contact.observed", body, "2026-10-06T10:00:00", status),
        )
    conn.execute(
        "INSERT INTO evidence_uploads (evidence_id, job_id, run_id, local_evidence_id,"
        " metadata_json, created_at, status) VALUES ('s1', 'job-1', 'run-1', 'l1', '{}', ?, ?)",
        ("2026-10-06T10:00:00", "pending"),
    )
    conn.commit()


def test_the_old_queue_becomes_expired_on_the_next_start(tmp_path: Path) -> None:
    path = tmp_path / "collector.db"
    conn = storage.connect(path)
    _old_rows(conn)
    conn.close()

    conn = storage.connect(path)  # the first start after the update
    try:
        states = dict(conn.execute("SELECT event_id, status FROM outbox").fetchall())
        assert states == {"e1": "expired", "e2": "expired", "e3": "expired", "e4": "accepted"}, (
            "waiting, pending and refused rows expire; what ARGUS accepted stays accepted"
        )
        upload = conn.execute("SELECT status FROM evidence_uploads").fetchone()[0]
        assert upload == "expired"
        pending, errors, expired = repo.totals(conn)
        assert (pending, errors) == (0, 0), "the queue starts at zero"
        assert expired == 4, "3 events + 1 snapshot"
        assert repo.pending_events(conn, "run-1", 50) == [], "nothing of it is ever sent again"
        assert repo.pending_runs(conn) == []
        assert delivery.job_totals(conn, "job-1") == (0, 0)
    finally:
        conn.close()
