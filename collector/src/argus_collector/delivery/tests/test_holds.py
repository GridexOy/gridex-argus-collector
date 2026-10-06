"""A run ARGUS refused as a whole waits and is asked again; the delivery threads never
die (owner 06.10.2026: nothing leaves the outbox but accepted / duplicate)."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import pytest

from argus_collector.delivery import contract as delivery
from argus_collector.delivery import service
from argus_collector.delivery.holds import Holds
from argus_collector.delivery.tests.test_reasons import TARGET, Recorder


def test_a_held_run_waits_and_is_released_on_success() -> None:
    holds = Holds()
    holds.hold("r1", "permanent")
    assert holds.held("r1") and not holds.held("r2") and holds.refused()
    holds.release("r1")
    assert not holds.held("r1") and not holds.refused()
    holds.hold("r2", "lease")
    assert holds.held("r2") and not holds.refused(), "a lease is reconciled, no error shown"


def test_a_pass_that_raises_does_not_end_the_thread(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_COLLECTOR_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(service, "MAX_BACKOFF_S", 0.1)
    passes = {"n": 0}

    def tick(self: delivery.Deliverer, conn: sqlite3.Connection, *args: object) -> float:
        passes["n"] += 1
        if passes["n"] == 1:
            raise KeyError("an answer the collector did not expect")
        return 0.05

    monkeypatch.setattr(delivery.Deliverer, "tick", tick)
    deliverer = delivery.Deliverer(tmp_path / "c.sqlite3", lambda: TARGET, Recorder())
    deliverer.start()
    try:
        deadline = time.monotonic() + 5
        while passes["n"] < 6 and time.monotonic() < deadline:
            time.sleep(0.05)
        assert passes["n"] >= 6 and all(t.is_alive() for t in deliverer._threads)
    finally:
        deliverer.stop()
    log = "".join(p.read_text("utf-8") for p in (tmp_path / "home" / "logs").glob("*"))
    assert "delivery: pass failed, the outbox waits: KeyError" in log


def test_two_threads_open_a_new_database_at_once(tmp_path: Path) -> None:
    """The first start after an update with a migration: both lanes open the database."""
    import threading

    from argus_collector.storage import contract as storage

    errors: list[BaseException] = []

    def open_it() -> None:
        try:
            storage.connect(tmp_path / "fresh.sqlite3").close()
        except BaseException as exc:  # noqa: BLE001 - the test collects them
            errors.append(exc)

    threads = [threading.Thread(target=open_it) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
