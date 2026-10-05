"""0.4.8.5 (owner 05.10.2026): an event ARGUS keeps rejecting as evidence_missing is given up
after its snapshot proves missing; a stand-in takes its seq and the rest of the run goes on."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from argus_collector.api_client import contract as api
from argus_collector.delivery import contract as delivery
from argus_collector.delivery import repository as repo
from argus_collector.storage import contract as storage

from collector.tests.contract.conftest import Argus
from collector.tests.contract.system import company
from collector.tests.contract.worker import claim, phone_contact, started


class Hooks:
    def __init__(self, token: str) -> None:
        self.token, self.rejected_items = token, []  # type: list[tuple[str, str, str]]

    def token_for(self, conn: sqlite3.Connection, job_id: str, run_id: str) -> str | None:
        return self.token

    def lease_problem(self, job_id: str, run_id: str, code: str, token: str) -> None:
        return None

    def rejected(self, conn: sqlite3.Connection, job_id: str, kind: str, code: str,
                 item: str) -> None:
        self.rejected_items.append((kind, code, item))

    def applied(self, conn: sqlite3.Connection, job_id: str, resp: api.EventsResponse) -> None:
        return None


def queue(conn: sqlite3.Connection, job: api.ClaimedJob, events: list[api.Event]) -> None:
    """The outbox: a contact on a snapshot that was queued but whose files are gone since."""
    for event in events:
        evidence = ["snapshot-lost-here"] if event.type == "contact.observed" else []
        repo.insert_event(conn, (event.event_id, job.job.job_id, job.lease.run_id, event.seq),
                          event.type, api.to_json(event), evidence)
    metadata = {"evidence_id": "snapshot-lost-here", "final_url": "https://fixture.example/team"}
    repo.insert_upload(conn, ("snapshot-lost-here", job.job.job_id, job.lease.run_id,
                              "files-deleted"), metadata)
    conn.commit()


def test_lost_snapshot_is_given_up_and_the_run_goes_on(
    argus: Argus, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ARGUS_COLLECTOR_HOME", str(tmp_path / "home"))
    argus.system.batch([company()])
    job = claim(argus)[0]
    contact = phone_contact(job, 1, "snapshot-lost-here")
    db = tmp_path / "c.sqlite3"
    conn = storage.connect(db)
    try:
        queue(conn, job, [contact, started(job, 2)])
        hooks = Hooks(job.lease.execution_token)
        target = delivery.ApiTarget(argus.base_url, argus.worker_id, argus.token, argus.proxy)
        deliverer = delivery.Deliverer(db, lambda: target, hooks)
        for _ in range(3):
            deliverer.flush()
            deliverer.tick(conn)
        rows = {r["seq"]: r for r in conn.execute("SELECT * FROM outbox ORDER BY seq")}
    finally:
        conn.close()
    assert hooks.rejected_items == [
        ("evidence", "evidence_missing", "evidence snapshot-lost-here"),
        ("contact.observed", "evidence_missing",
         f"event {contact.event_id} seq 1 (snapshot snapshot-lost-here is not stored here)"),
    ], "the upload fails here, ARGUS refuses the event once, then it is given up"
    stand_in = rows[1]
    assert (stand_in["type"], stand_in["status"]) == ("source.blocked", "accepted")
    assert stand_in["replaced_type"] == "contact.observed"
    assert stand_in["replaced_event_id"] == contact.event_id
    payload = json.loads(stand_in["event_json"])["payload"]
    assert (payload["status"], payload["url"]) == ("evidence_missing", "https://fixture.example/team")
    assert rows[2]["status"] == "accepted", "the event after the lost one reached ARGUS"
    assert deliverer.pending == 0
