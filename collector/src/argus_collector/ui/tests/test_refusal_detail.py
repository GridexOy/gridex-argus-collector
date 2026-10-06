"""Contract 3.1.0 (wire 1.2): a refusal names its rule, observation and field (0.4.8.7)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from argus_collector.api_client import contract as api
from argus_collector.delivery import contract as delivery
from argus_collector.delivery import results
from argus_collector.storage import contract as storage
from argus_collector.ui import queue_lines, repository

MESSAGE = ("observation o3 (email): a person observation without full_name in this event;"
           " enrichment needs the person's name")


class Recorder:
    """The delivery hooks the results need (the scheduler's are tested in scheduler)."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str, str]] = []

    def rejected(self, conn: sqlite3.Connection, job_id: str, kind: str, code: str,
                 item: str) -> None:
        self.calls.append((job_id, kind, code, item))

    def applied(self, conn: sqlite3.Connection, job_id: str, resp: api.EventsResponse) -> None:
        return None


def outbox(conn: sqlite3.Connection, seq: int) -> str:
    with conn:
        conn.execute(
            "INSERT INTO outbox (event_id, job_id, run_id, seq, type, event_json,"
            " evidence_ids_json, created_at) VALUES (?, 'j1', 'r1', ?, 'contact.observed', '{}',"
            " '[\"ev1\"]', '2026-10-06T10:00:00+00:00')", (f"e{seq}", seq))
    return f"e{seq}"


def journal(home: Path) -> str:
    return "".join(p.read_text("utf-8") for p in (home / "logs").glob("*.log"))


def answer() -> api.EventsResponse:
    """The rejected result of `docs/collector_contract/events.response.v1_2.json`."""
    return api.from_json(api.EventsResponse, {
        "results": [
            {"event_id": "e1", "seq": 1, "status": "accepted", "code": None,
             "canonical_contact_id": None, "server_revision": 2, "state_applied": True,
             "channel_status": None, "detail": None},
            {"event_id": "e2", "seq": 2, "status": "rejected", "code": "invalid_input",
             "canonical_contact_id": None, "server_revision": 2, "state_applied": False,
             "channel_status": None,
             "detail": {"rule": "person_without_name", "observation_id": "o3",
                        "field": "email", "message": MESSAGE}},
        ],
        "last_contiguous_seq": 2, "job_state": "running", "next_run_scheduled": False,
    })


@pytest.fixture
def home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("ARGUS_COLLECTOR_HOME", str(tmp_path / "home"))
    return tmp_path / "home"


def test_the_rule_reaches_the_journal_jono_and_lahetys(home: Path, tmp_path: Path) -> None:
    conn = storage.connect(tmp_path / "c.sqlite3")
    try:
        ids = [outbox(conn, seq) for seq in (1, 2)]
        rows = {r["event_id"]: r for r in conn.execute("SELECT * FROM outbox")}
        hooks = Recorder()
        results.apply(conn, hooks, "j1", rows, answer())  # type: ignore[arg-type]
        assert hooks.calls == [("j1", "contact.observed", "invalid_input/person_without_name",
                                f"event {ids[1]} seq 2 [o3 email: {MESSAGE[:160]}]")]
        assert delivery.stats(conn).last_code == "invalid_input/person_without_name"
        assert delivery.reason("invalid_input/person_without_name") == (
            "a person event without the person's name")
        msgs = repository.load_messages()
        assert queue_lines.rejection_text(msgs, "invalid_input/person_without_name") == (
            "henkilöltä puuttuu nimi")
        assert queue_lines.rejection_text(msgs, "invalid_input") == msgs.t(
            "delivery.rejected.invalid_input"), "a 1.1 refusal keeps the code's words"
        assert "1 accepted/duplicate, 1 rejected" in journal(home)
    finally:
        conn.close()


def test_heartbeat_offers_both_schemas() -> None:
    from argus_collector.ui import heartbeat_call  # noqa: PLC0415 - the panel side

    assert heartbeat_call.SCHEMA_VERSIONS == ["1.1", "1.2"]
