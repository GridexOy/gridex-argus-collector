"""The one transport state of Lähetys (owner 05.10.2026, 0.4.8.2).

Heartbeats and delivery requests are two signals of the same link to ARGUS.
`Ei verkkoa` (offline) only when neither got an answer: the last heartbeat got
none, and the last delivery request got none either or none was answered since
the heartbeat went down (an empty outbox sends nothing). A delivery request
without an answer while heartbeats pass is a retry, not offline; a delivery
answer while heartbeats time out means the link works. Any HTTP answer counts,
an error status too. Every change of the state is one journal line, written
here and nowhere else, whichever thread (heartbeat or delivery) sees it first.
"""

from __future__ import annotations

import threading
import time

from argus_collector.runtime import contract as runtime

OFFLINE = "offline"


class Transport:
    def __init__(self) -> None:
        self.heartbeat_down_since: float | None = None  # monotonic; None: last one answered
        self.answered_at = 0.0  # monotonic time of the last delivery request ARGUS answered
        self.delivery_down = False  # the last delivery request got no answer
        self._noted = OFFLINE
        self._lock = threading.Lock()

    def heartbeat(self, answered: bool) -> None:
        if answered:
            self.heartbeat_down_since = None
        elif self.heartbeat_down_since is None:
            self.heartbeat_down_since = time.monotonic()

    def answered(self) -> None:
        """A delivery request got an HTTP answer (any status)."""
        self.answered_at, self.delivery_down = time.monotonic(), False

    def no_answer(self) -> None:
        """A delivery request got no answer at all."""
        self.delivery_down = True

    @property
    def silent(self) -> bool:
        """Neither the heartbeat nor delivery got an answer since the heartbeat went down."""
        down = self.heartbeat_down_since
        return down is not None and (self.delivery_down or self.answered_at < down)

    def note(self, state: str, why: str = "") -> bool:
        """One journal line per change of `state`; False when it did not change."""
        with self._lock:
            before = self._noted
            if state == before:
                return False
            self._noted = state
        runtime.journal("delivery", f"transport {before} -> {state}{why}")
        return True
