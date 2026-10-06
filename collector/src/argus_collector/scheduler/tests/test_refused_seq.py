"""WINLOG 06.10.2026 (MAIN-PC, question 9): ARGUS refused Sonepar seq 61-101 and Tele-Tukku
28-34 as invalid_input without taking their seq; the tail waited for them for ever,
7540 sequence_gap retries about once a second, and the stand-ins on 99-101 were refused
too. A final refusal of any code whose seq ARGUS did not take gives the seq to a filler
(source.blocked, then a copy of the run's last job.progress); a run that only gets
sequence_gap waits a backoff."""

from __future__ import annotations

import sqlite3
import time
from collections import Counter
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from argus_collector.api_client import contract as api
from argus_collector.delivery import contract as delivery
from argus_collector.scheduler import events
from argus_collector.scheduler.tests.stands import System, make_collector
from argus_collector.storage import contract as storage
from contract_server import events as stand_events
from contract_server import server as contract_server
from contract_server.event_context import rejected
from test_site import server

PROGRESS = {
    "stage": "browser", "active_seconds": 1.0, "transport_state": "online",
    "counts": {k: 0 for k in ("persons", "organization_channels", "other_entities",
                              "observations", "pages_processed", "browser_actions",
                              "evidence_count", "gaps", "outbox_pending", "states_processed")},
    "coverage": {"frontier_status": "partial", "confirmation": "unverified", "basis": "unknown",
                 "scope_description": "", "expected_count": None, "found_count": 0,
                 "gap_count": 0, "evidence_ids": []},
}


def queue(conn: sqlite3.Connection, job_id: str, run_id: str, site: ThreadingHTTPServer) -> None:
    """started, progress, a page, then 4 more events (seq 4 and 5 are the refused ones)."""
    payload = api.from_json(api.ProgressPayload, PROGRESS)
    page = (f"src-{run_id}", server.base_url(site), "k1", None, "extracted")
    makers = [events.started(job_id, run_id, "t"),
              events.envelope(api.JobProgressEvent, job_id, run_id, payload),
              events.source_event("processed", job_id, run_id, page)([])]
    makers += [events.started(job_id, run_id, "t") for _ in range(4)]
    for make in makers:
        delivery.enqueue_event(conn, job_id, run_id, make, [])
    conn.commit()


def argus_0_4_24(refused: Counter[str]) -> Any:
    """seq 4 and 5 refused without their seq; the first source.blocked filler too."""
    real = stand_events.evaluate

    def evaluate(batch: Any, event: dict[str, Any]) -> Any:
        kind = event["type"]
        if event["seq"] in (4, 5) and kind == "job.started" or (
                kind == "source.blocked" and not refused["source.blocked"]):
            refused[kind] += 1
            return rejected("invalid_input", "refused", record=False)
        return real(batch, event)

    return evaluate


def test_a_refused_seq_is_filled_and_the_tail_goes_on(
    tmp_path: Path, argus: contract_server.ContractServer, site: ThreadingHTTPServer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_COLLECTOR_HOME", str(tmp_path / "home"))
    job_id = System(argus).batch(site, ["fixture_oy"])["fixture_oy"]
    collector = make_collector(tmp_path, argus, "http://127.0.0.1:9/v1")
    conn = storage.connect(tmp_path / "collector.db")
    target = collector.target()
    assert target is not None
    collector._claim(conn, target)
    queue(conn, job_id, conn.execute("SELECT run_id FROM jobs").fetchone()[0], site)
    refused, requests, post = Counter[str](), Counter[str](), api.post_events
    monkeypatch.setattr(stand_events, "evaluate", argus_0_4_24(refused))
    monkeypatch.setattr(api, "post_events",
                        lambda *a, **k: (requests.update(["events"]), post(*a, **k))[1])
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline and _left(conn):
        collector.deliverer.flush()
        collector.deliverer.tick(conn)
        time.sleep(0.1)
    rows = [tuple(r) for r in conn.execute(
        "SELECT seq, type, status, replaced_type FROM outbox ORDER BY seq")]
    conn.close()
    assert [r[:3] for r in rows] == [
        (1, "job.started", "accepted"), (2, "job.progress", "accepted"),
        (3, "source.processed", "accepted"), (4, "job.progress", "accepted"),
        (5, "source.blocked", "accepted"), (6, "job.started", "accepted"),
        (7, "job.started", "accepted")], rows
    assert [r[3] for r in rows][3:5] == ["job.started", "job.started"], "what each seq lost"
    assert refused == {"job.started": 2, "source.blocked": 1}
    assert requests["events"] < 25, f"{requests['events']} requests: no loop without a pause"
    assert collector.queue_view().rows[0].rejected == 2, "Hylätty 2: a refused filler is no loss"


def _left(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT count(*) FROM outbox WHERE status IN ('pending', 'waiting')"
                            ).fetchone()[0])


def test_a_tail_stuck_before_0_4_8_9_goes_on(
    tmp_path: Path, argus: contract_server.ContractServer, site: ThreadingHTTPServer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The MAIN-PC outbox of 06.10: seq 3 already `rejected` (ARGUS never took it), the tail
    after it pending - the first pass of the new version fills seq 3 and the tail goes."""
    monkeypatch.setenv("ARGUS_COLLECTOR_HOME", str(tmp_path / "home"))
    job_id = System(argus).batch(site, ["fixture_oy"])["fixture_oy"]
    collector = make_collector(tmp_path, argus, "http://127.0.0.1:9/v1")
    conn = storage.connect(tmp_path / "collector.db")
    target = collector.target()
    assert target is not None
    collector._claim(conn, target)
    run_id = conn.execute("SELECT run_id FROM jobs").fetchone()[0]
    page = (f"src-{run_id}", server.base_url(site), "k1", None, "extracted")
    for make in (events.started(job_id, run_id, "t"),
                 events.source_event("processed", job_id, run_id, page)([])):
        delivery.enqueue_event(conn, job_id, run_id, make, [])
    conn.commit()
    collector.deliverer.flush()
    collector.deliverer.tick(conn)  # ARGUS takes seq 1-2
    for _ in range(3):
        delivery.enqueue_event(conn, job_id, run_id, events.started(job_id, run_id, "t"), [])
    conn.execute("UPDATE outbox SET status = 'rejected', code = 'invalid_input' WHERE seq = 3")
    conn.commit()
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline and _left(conn):
        collector.deliverer.flush()
        collector.deliverer.tick(conn)
        time.sleep(0.1)
    rows = [tuple(r) for r in conn.execute("SELECT seq, type, status FROM outbox ORDER BY seq")]
    conn.close()
    assert rows == [(1, "job.started", "accepted"), (2, "source.processed", "accepted"),
                    (3, "source.blocked", "accepted"), (4, "job.started", "accepted"),
                    (5, "job.started", "accepted")], rows
    assert collector.queue_view().rows[0].rejected == 0, "its loss was counted before"
