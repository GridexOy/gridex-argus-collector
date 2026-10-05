"""Lahetys follows the heartbeat: no answer is `offline` also with nothing to send."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from argus_collector.api_client import contract as api
from argus_collector.delivery import contract as delivery
from argus_collector.storage import contract as storage

TARGET = delivery.ApiTarget("http://127.0.0.1:9/api/collector", "worker-1", "token", "direct")


class NoJobs:
    def token_for(self, conn: sqlite3.Connection, job_id: str, run_id: str) -> str | None:
        return None

    def lease_problem(self, job_id: str, run_id: str, code: str, token: str) -> None:
        return None

    def rejected(self, conn: sqlite3.Connection, job_id: str, kind: str, code: str,
                 item: str) -> None:
        return None

    def applied(self, conn: sqlite3.Connection, job_id: str, resp: api.EventsResponse) -> None:
        return None


def test_heartbeat_without_answer_shows_offline_until_answered(tmp_path: Path) -> None:
    db = tmp_path / "state" / "collector.sqlite3"
    changes: list[str] = []
    deliverer = delivery.Deliverer(db, lambda: TARGET, NoJobs(), lambda: changes.append("x"))
    conn = storage.connect(db)
    try:
        deliverer.tick(conn)
        assert deliverer.state == "synced", "an empty outbox is sent"
        deliverer.link(False)
        assert deliverer.state == "offline" and changes, "the panel is told at once"
        deliverer.tick(conn)
        assert deliverer.state == "offline", "an idle pass does not hide the outage"
        deliverer.link(True)
        assert deliverer.state == "synced"
    finally:
        conn.close()


def test_answer_after_a_failed_send_retries_now(tmp_path: Path) -> None:
    deliverer = delivery.Deliverer(tmp_path / "c.sqlite3", lambda: TARGET, NoJobs())
    deliverer.error, deliverer.failures, deliverer.pending = "offline", 4, 3
    assert deliverer.state == "offline"
    deliverer.link(True)
    assert deliverer.failures == 0 and deliverer._wake.is_set(), "no wait for the backoff"
