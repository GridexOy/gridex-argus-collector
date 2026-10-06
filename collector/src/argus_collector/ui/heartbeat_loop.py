"""The heartbeat clock of Yhteys (owner 05.10.2026, 0.4.8.2).

One thread sends every heartbeat: an attempt every 30 s counted from the start
of the previous one, whatever the previous answer was (time-out, 5xx, 401, an
error inside the panel). `now()` sends one at once (Yhdistä, Yhdistä
uudelleen) and the 30 s count starts again from it. Nothing a heartbeat raises
stops the clock; if the thread dies anyway, `ensure()` - called by the panel
every second - starts it again and says so in the journal.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

from argus_collector.runtime import contract as runtime

HEARTBEAT_INTERVAL_S = 30.0
HEARTBEAT_TIMEOUT_S = 30.0  # read time-out of one heartbeat request


class HeartbeatLoop:
    def __init__(self, beat: Callable[[], None], interval_s: float | None = None) -> None:
        self.beat = beat
        self.interval_s = HEARTBEAT_INTERVAL_S if interval_s is None else interval_s
        self._wake, self._stop = threading.Event(), threading.Event()
        self._thread: threading.Thread | None = None
        self._started: float | None = None  # monotonic start of the attempt in flight
        self.restarts = 0

    @property
    def alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def ensure(self) -> None:
        """Start the clock, or start it again when its thread died."""
        if self._stop.is_set() or self.alive:
            return
        if self._thread is not None:
            self.restarts += 1
            runtime.journal("http", "heartbeat: the clock had stopped, started again")
        self._thread = threading.Thread(target=self._run, name="heartbeat-loop", daemon=True)
        self._thread.start()

    def now(self) -> None:
        """One heartbeat at once; the next ones every 30 s after it."""
        self._wake.set()
        self.ensure()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()

    def running_for(self) -> float:
        """Seconds the attempt in flight has run (0 when none is)."""
        started = self._started
        return 0.0 if started is None else time.monotonic() - started

    def _run(self) -> None:
        while not self._stop.is_set():
            self._wake.clear()
            started = self._started = time.monotonic()
            try:
                self.beat()
            except Exception as exc:  # the clock never stops on an error (owner 05.10.2026)
                runtime.journal("http", f"heartbeat: {type(exc).__name__} in the panel:"
                                f" {str(exc)[:160]}")
            finally:
                self._started = None
            self._wake.wait(max(0.0, self.interval_s - (time.monotonic() - started)))
