"""Pair A3.1: restart, lost lease and network outage end without duplicates."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from argus_collector.scheduler import contract as scheduler
from argus_collector.scheduler.tests.stands import (
    System,
    gold,
    heartbeat,
    make_collector,
    wait_for,
)
from collector.tests.fake_model_server import FakeModelServer
from contract_server import server as contract_server

DONE = ("completed", "partial", "failed", "cancelled")
PERSONS = len(gold("fixture_oy")["persons"])


def local_persons(collector: scheduler.Collector) -> int:
    rows = collector.queue_view().rows
    return rows[0].persons if rows else 0


def finish(collector: scheduler.Collector, system: System, job_id: str) -> None:
    wait_for(lambda: system.job(job_id)["state"] in DONE)
    wait_for(lambda: collector.delivery_view().pending == 0)
    collector.stop()
    collector.deliverer.stop()


def assert_clean(system: System, job_id: str) -> None:
    view = system.contacts(job_id)
    assert view["rejected"] == []
    people = [c for c in view["contacts"] if c["entity_type"] == "person"]
    assert len(people) == PERSONS, "no person twice, none lost"
    status = system.job(job_id)
    assert status["state"] == "completed" and status["runs_completed"] == 1
    assert status["counts"]["persons"] == PERSONS


def test_panel_restart_mid_walk_resumes_the_same_run(
    tmp_path: Path, argus: contract_server.ContractServer, site: ThreadingHTTPServer,
    model: FakeModelServer,
) -> None:
    system = System(argus)
    job_id = system.batch(site, ["fixture_oy"])["fixture_oy"]
    first = make_collector(tmp_path, argus, model.endpoint)
    first.deliverer.start()
    first.start()
    wait_for(lambda: local_persons(first) >= 2)
    run_id = system.job(job_id)["current_run_id"]
    first.stop()
    wait_for(lambda: not first.walking)
    first.deliverer.stop()
    assert first.queue_view().rows[0].state == "stopped"
    second = make_collector(tmp_path, argus, model.endpoint)  # the panel opened again
    second.deliverer.start()
    second.start()
    finish(second, system, job_id)
    assert system.job(job_id)["current_run_id"] == run_id, "seq and run continue"
    assert_clean(system, job_id)


class Clock:
    """ARGUS's clock for the stand: real time plus a jump the test controls."""

    def __init__(self) -> None:
        self.offset = timedelta(0)

    def __call__(self) -> datetime:
        return datetime.now(UTC) + self.offset


def test_expired_lease_is_reconciled_and_the_walk_goes_on(
    tmp_path: Path, site: ThreadingHTTPServer, model: FakeModelServer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_COLLECTOR_HOME", str(tmp_path / "home"))
    clock = Clock()
    argus = contract_server.start(port=0, now=clock)
    try:
        system = System(argus)
        job_id = system.batch(site, ["fixture_oy"])["fixture_oy"]
        collector = make_collector(tmp_path, argus, model.endpoint)
        collector.deliverer.start()
        collector.start()
        wait_for(lambda: local_persons(collector) >= 1)
        clock.offset = timedelta(seconds=600)  # ARGUS sees the 180 s lease run out
        heartbeat(collector, argus)  # answers `expired`: the walk stops, then reconciles
        finish(collector, system, job_id)
        assert_clean(system, job_id)
        log = "".join(p.read_text("utf-8") for p in (tmp_path / "home" / "logs").glob("*"))
        assert "reconcile job" in log and ": resume," in log, "the lease really expired"
    finally:
        argus.shutdown()
        argus.server_close()


def test_argus_down_and_back_delivers_everything_once(
    tmp_path: Path, site: ThreadingHTTPServer, model: FakeModelServer
) -> None:
    state = tmp_path / "argus-state.json"
    argus = contract_server.start(port=0, state_path=state)
    port = argus.server_address[1]
    system = System(argus)
    job_id = system.batch(site, ["fixture_oy"])["fixture_oy"]
    collector = make_collector(tmp_path, argus, model.endpoint)
    collector.deliverer.start()
    collector.start()
    wait_for(lambda: local_persons(collector) >= 1)
    argus.shutdown()
    argus.server_close()
    collector.heartbeat_failed(0)  # the panel's heartbeat gets no answer either
    wait_for(lambda: collector.deliverer.state == "offline")
    wait_for(lambda: collector.queue_view().rows[0].state in DONE, timeout_s=180)
    assert collector.delivery_view().pending > 0, "the walk went on, results wait"
    back = contract_server.start(port=port, state_path=state)
    try:
        finish(collector, System(back), job_id)
        assert_clean(System(back), job_id)
    finally:
        back.shutdown()
        back.server_close()
