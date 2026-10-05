"""evidence_missing (owner 05.10.2026, 0.4.8.5): snapshot first, at most 3 retries with the same
code, then given up; sequence_gap is not counted; a seq ARGUS kept needs no stand-in."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from argus_collector.api_client import contract as api
from argus_collector.delivery import contract as delivery
from argus_collector.delivery import repository as repo
from argus_collector.delivery import results, retry
from argus_collector.delivery.tests.test_reasons import Recorder, answer, journal
from argus_collector.evidence import contract as evidence
from argus_collector.storage import contract as storage


@pytest.fixture
def conn(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> sqlite3.Connection:
    monkeypatch.setenv("ARGUS_COLLECTOR_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(evidence, "load_snapshot", lambda c, local: object())  # stored
    found = storage.connect(tmp_path / "c.sqlite3")
    repo.insert_upload(found, ("ev1", "j1", "r1", "local-1"),
                       {"final_url": "https://acme.example/contact"})
    repo.insert_event(found, ("e5", "j1", "r1", 5), "contact.observed", {}, ["ev1"])
    found.commit()
    repo.mark_upload(found, "ev1", "duplicate", "")
    return found


def refuse(conn: sqlite3.Connection, hooks: Recorder, code: str, last_seq: int = 4) -> sqlite3.Row:
    rows = {r["event_id"]: r for r in conn.execute("SELECT * FROM outbox")}
    event_id = next(iter(rows))
    data = api.to_json(answer((event_id, 5, "rejected", code)))
    resp = api.from_json(api.EventsResponse, {**data, "last_contiguous_seq": last_seq})
    results.apply(conn, hooks, "j1", rows, resp)
    row: sqlite3.Row = conn.execute("SELECT * FROM outbox").fetchone()
    return row


def test_three_retries_snapshot_first_then_given_up(
    conn: sqlite3.Connection, tmp_path: Path
) -> None:
    hooks = Recorder()
    for count in (1, 2, 3):
        row = refuse(conn, hooks, "evidence_missing")
        assert (row["status"], row["retry_count"]) == ("pending", count)
        assert repo.upload_states(conn, ["ev1"]) == {"ev1": "pending"}, "snapshot first"
        repo.mark_upload(conn, "ev1", "duplicate", "")  # uploaded again, ARGUS still refuses
    row = refuse(conn, hooks, "evidence_missing")
    assert hooks.calls == [("j1", "contact.observed", "evidence_missing",
                            "event e5 seq 5 (evidence_missing after 3 retries)")]
    assert (row["type"], row["status"], row["seq"]) == ("source.blocked", "pending", 5)
    assert (row["replaced_type"], row["replaced_event_id"]) == ("contact.observed", "e5")
    stand_in = api.event_from_json(json.loads(row["event_json"]))
    assert stand_in.payload.url == "https://acme.example/contact"  # type: ignore[union-attr]
    assert delivery.stats(conn).errors == 1 and delivery.stats(conn).last_code == "evidence_missing"
    assert [(r.kind, r.item_id) for r in delivery.rejections(conn)] == [("contact.observed", "e5")]
    log = journal(tmp_path / "home")
    assert "retry 1 of 3" in log and "retry 3 of 3" in log and "was {'ev1': 'duplicate'}" in log
    assert "seq 5 carries source.blocked" in log


def test_a_seq_argus_kept_is_just_rejected(conn: sqlite3.Connection) -> None:
    hooks = Recorder()
    retry.give_up(conn, hooks, "j1", conn.execute("SELECT * FROM outbox").fetchone(),
                  "evidence_missing", 5, "test")
    row = conn.execute("SELECT * FROM outbox").fetchone()
    assert (row["type"], row["status"]) == ("contact.observed", "rejected")
    assert row["replaced_type"] == "", "no stand-in: ARGUS counted the seq already"


def test_sequence_gap_is_not_counted(conn: sqlite3.Connection) -> None:
    hooks = Recorder()
    for _ in range(6):
        row = refuse(conn, hooks, "sequence_gap")
    assert (row["status"], row["retry_count"], hooks.calls) == ("pending", 0, [])
