"""Lahetys follows the heartbeat: no answer is `offline` also with nothing to send."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

import pytest

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


def test_one_journal_line_per_transport_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ARGUS_COLLECTOR_HOME", str(tmp_path / "home"))
    db = tmp_path / "c.sqlite3"
    deliverer = delivery.Deliverer(db, lambda: TARGET, NoJobs())
    conn = storage.connect(db)
    try:
        for _ in range(3):
            deliverer.tick(conn)
        deliverer.link(False)
        threads = [threading.Thread(target=deliverer.tick, args=(storage.connect(db),))
                   for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        answers = [threading.Thread(target=deliverer.link, args=(True,)) for _ in range(4)]
        for thread in answers:
            thread.start()
        for thread in answers:
            thread.join()
        deliverer.tick(conn)
    finally:
        conn.close()
    log = "".join(p.read_text("utf-8") for p in (tmp_path / "home" / "logs").glob("*.log"))
    lines = [line.split(" ", 1)[1] for line in log.splitlines() if "transport" in line]
    assert lines == [
        "delivery: transport offline -> synced",
        "delivery: transport synced -> offline (heartbeat)",
        "delivery: transport offline -> synced (heartbeat)",
    ], "each change once, whichever thread saw it"
