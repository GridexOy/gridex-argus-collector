"""A rejection reaches the company's row and the journal with company, id and words."""

from __future__ import annotations

from pathlib import Path

import pytest

from argus_collector.scheduler import hooks
from argus_collector.scheduler import repository as repo
from argus_collector.storage import contract as storage

JOB = {
    "job_id": "j1", "batch_id": "b1", "company_id": "c1", "company_name": "Ellego Oy",
    "definition_json": "{}", "state": "running", "stage": "browser", "run_id": "r1",
    "lease_token": "t", "lease_generation": 1, "lease_expires_at": "2026-10-05T12:00:00+00:00",
}


def test_rejected_counts_and_journals_the_company(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ARGUS_COLLECTOR_HOME", str(tmp_path / "home"))
    conn = storage.connect(tmp_path / "c.sqlite3")
    try:
        with conn:
            repo.insert_job_tx(conn, JOB)
            conn.execute(
                "INSERT INTO outbox (event_id, job_id, run_id, seq, type, event_json,"
                " evidence_ids_json, created_at, status, code, sent_at) VALUES ('e7', 'j1',"
                " 'r1', 7, 'contact.observed', '{}', '[]', '2026-10-05T10:00:00+00:00',"
                " 'rejected', 'participation_not_confirmed', '2026-10-05T10:00:01+00:00')"
            )
        changes: list[int] = []
        collector_hooks = hooks.CollectorHooks.__new__(hooks.CollectorHooks)
        collector_hooks.on_change = lambda: changes.append(1)
        collector_hooks.rejected(conn, "j1", "contact.observed", "participation_not_confirmed",
                                 "event e7 seq 7")
        row = repo.job(conn, "j1")
        assert row is not None and row["rejected"] == 1 and changes
        assert row["last_reject_code"] == "participation_not_confirmed"
        log = "".join(p.read_text("utf-8") for p in (tmp_path / "home" / "logs").glob("*.log"))
        assert ("delivery: job j1 (Ellego Oy): contact.observed event e7 seq 7 rejected"
                " participation_not_confirmed (participation is not confirmed)") in log
    finally:
        conn.close()

