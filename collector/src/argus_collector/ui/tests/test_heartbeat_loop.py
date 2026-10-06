"""The heartbeat clock (0.4.8.2): every interval from the start of the last attempt, whatever
the attempt did; `now()` at once; a dead thread is started again by `ensure()`."""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from argus_collector.ui.heartbeat_loop import HeartbeatLoop


@pytest.fixture(autouse=True)
def home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("ARGUS_COLLECTOR_HOME", str(tmp_path))
    return tmp_path


def wait_for(predicate: object, timeout_s: float = 5.0) -> None:
    deadline = time.monotonic() + timeout_s
    while not predicate() and time.monotonic() < deadline:  # type: ignore[operator]
        time.sleep(0.01)


def test_an_error_in_one_attempt_does_not_stop_the_clock(home: Path) -> None:
    calls: list[float] = []

    def beat() -> None:
        calls.append(time.monotonic())
        if len(calls) <= 2:
            raise RuntimeError("database is locked")

    loop = HeartbeatLoop(beat, interval_s=0.05)
    loop.ensure()
    wait_for(lambda: len(calls) >= 4)
    loop.stop()
    assert len(calls) >= 4, "the attempts after the errors still came"
    log = "".join(p.read_text("utf-8") for p in (home / "logs").glob("*.log"))
    assert "heartbeat: RuntimeError in the panel: database is locked" in log


def test_the_interval_counts_from_the_start_of_the_last_attempt() -> None:
    starts: list[float] = []

    def slow_beat() -> None:
        starts.append(time.monotonic())
        time.sleep(0.15)

    loop = HeartbeatLoop(slow_beat, interval_s=0.25)
    loop.ensure()
    wait_for(lambda: len(starts) >= 3)
    loop.stop()
    gaps = [b - a for a, b in zip(starts, starts[1:], strict=False)]
    assert all(0.2 <= gap < 0.35 for gap in gaps), gaps


def test_now_sends_at_once_and_one_thread_sends_all() -> None:
    threads: set[str] = set()
    calls: list[float] = []

    def beat() -> None:
        threads.add(threading.current_thread().name)
        calls.append(time.monotonic())

    loop = HeartbeatLoop(beat, interval_s=30.0)
    loop.ensure()
    wait_for(lambda: len(calls) == 1)
    for _ in range(3):
        loop.now()
        time.sleep(0.05)
    wait_for(lambda: len(calls) >= 4)
    loop.stop()
    assert len(calls) == 4, "each Yhdistä uudelleen is one attempt, at once"
    assert threads == {"heartbeat-loop"}, "never two heartbeat threads"


def test_a_dead_clock_is_started_again(home: Path) -> None:
    calls: list[int] = []
    loop = HeartbeatLoop(lambda: calls.append(1), interval_s=30.0)
    loop._thread = threading.Thread(target=lambda: None)  # a clock whose thread has ended
    loop._thread.start()
    loop._thread.join()
    assert not loop.alive
    loop.ensure()
    wait_for(lambda: calls)
    loop.stop()
    assert calls and loop.restarts == 1
    log = "".join(p.read_text("utf-8") for p in (home / "logs").glob("*.log"))
    assert "heartbeat: the clock had stopped, started again" in log
