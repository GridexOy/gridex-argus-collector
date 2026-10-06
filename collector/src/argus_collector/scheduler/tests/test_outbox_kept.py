"""Owner 06.10.2026 (15:05-15:10 UTC, 500/502): Tele-Tukku seq 28-34 and Sonepar 61-101
never reached ARGUS and were not sent again. Nothing leaves the outbox but accepted /
duplicate: an old run's events still go out after ARGUS handed the job out with a new
run, and a request ARGUS refuses as a whole keeps its events pending."""

from __future__ import annotations

import sqlite3
import time
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from argus_collector.api_client import contract as api
from argus_collector.delivery import contract as delivery
from argus_collector.scheduler import events
from argus_collector.scheduler.tests.stands import WORKER_ID, System, make_collector
from argus_collector.storage import contract as storage
from contract_server import server as contract_server
from contract_server.claim import new_run


def outbox(conn: sqlite3.Connection, job_id: str) -> list[tuple[str, int, str]]:
    rows = conn.execute("SELECT run_id, seq, status FROM outbox WHERE job_id = ? ORDER BY id",
                        (job_id,)).fetchall()
    return [(str(r[0]), int(r[1]), str(r[2])) for r in rows]


def queue(conn: sqlite3.Connection, job_id: str, run_id: str, n: int) -> None:
    for _ in range(n):
        delivery.enqueue_event(conn, job_id, run_id, events.started(job_id, run_id, "t"), [])
    conn.commit()


def drain(deliverer: delivery.Deliverer, conn: sqlite3.Connection, job_id: str) -> None:
    deadline = time.monotonic() + 20
    while any(s == "pending" for *_, s in outbox(conn, job_id)) and time.monotonic() < deadline:
        deliverer.flush()
        deliverer.tick(conn)
        time.sleep(0.2)


def test_an_old_run_is_drained_after_argus_hands_out_a_new_one(
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
    old = conn.execute("SELECT run_id FROM jobs WHERE job_id = ?", (job_id,)).fetchone()[0]
    queue(conn, job_id, old, 3)  # the tail the 500/502 kept from ARGUS
    stand = argus.stand
    with stand.lock:  # what ARGUS did after the lease ran out: the job again, a new run
        job = stand.state["jobs"][job_id]
        new_run(stand.state, job, WORKER_ID, None, stand.now())
        job["state"] = "queued"
    collector._claim(conn, target)
    current = conn.execute("SELECT run_id FROM jobs WHERE job_id = ?", (job_id,)).fetchone()[0]
    assert current != old, "the new run is stored"
    queue(conn, job_id, current, 1)
    drain(collector.deliverer, conn, job_id)
    rows = outbox(conn, job_id)
    conn.close()
    assert [s for *_, s in rows] == ["accepted"] * 4, rows
    taken = [e for e in stand.state["events"].values() if e["run_id"] == old]
    assert sorted(e["seq"] for e in taken) == [1, 2, 3], "the old run reached ARGUS"
    log = "".join(p.read_text("utf-8") for p in (tmp_path / "home" / "logs").glob("*"))
    assert f"reconcile old run {old} of job {job_id}: drain_only" in log


def test_a_request_refused_as_a_whole_keeps_its_events(
    tmp_path: Path, argus: contract_server.ContractServer, site: ThreadingHTTPServer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_COLLECTOR_HOME", str(tmp_path / "home"))
    ids = System(argus).batch(site, ["fixture_oy", "nordtec"])
    collector = make_collector(tmp_path, argus, "http://127.0.0.1:9/v1")
    conn = storage.connect(tmp_path / "collector.db")
    target = collector.target()
    assert target is not None
    collector._claim(conn, target)
    runs = dict(conn.execute("SELECT job_id, run_id FROM jobs").fetchall())
    for job_id, run_id in runs.items():
        queue(conn, job_id, run_id, 2)
    real, refused = api.post_events, {"n": 0}

    def deploying(base: str, token: str, job_id: str, *args: Any, **kwargs: Any) -> Any:
        if job_id == ids["fixture_oy"] and refused["n"] < 3:  # a 404 while ARGUS restarts
            refused["n"] += 1
            raise api.ApiError(404, api.Error("not_found", "unknown job", False, "r"), None, "")
        return real(base, token, job_id, *args, **kwargs)

    monkeypatch.setattr(api, "post_events", deploying)
    deliverer = collector.deliverer
    deliverer.flush()
    deliverer.tick(conn)
    assert [s for *_, s in outbox(conn, ids["nordtec"])] == ["accepted"] * 2, "the other run"
    assert [s for *_, s in outbox(conn, ids["fixture_oy"])] == ["pending"] * 2
    assert deliverer.state == "delivery_error", "Lähetys says so while the run waits"
    drain(deliverer, conn, ids["fixture_oy"])
    rows = outbox(conn, ids["fixture_oy"])
    conn.close()
    assert [s for *_, s in rows] == ["accepted"] * 2 and refused["n"] == 3
    assert delivery.stats(storage.connect(tmp_path / "collector.db")).errors == 0
