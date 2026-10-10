"""The delivery threads: events in seq order on one, snapshots on the other, results back.

Independent of the walk (TZ_SELAIN 8.1 p.4): they run while a connection is
saved, also after Pysayta or a STOP file, until the outbox is empty. Events do
not wait for the snapshot lane (WINLOG 06.10.2026: ARGUS takes 3-5 s per new
snapshot); a page's events leave once its closing event is written.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from argus_collector.api_client import contract as api
from argus_collector.delivery import counters, results, retry, service
from argus_collector.delivery import repository as repo
from argus_collector.delivery.holds import Holds
from argus_collector.delivery.hooks import ApiTarget, DeliveryHooks, Failed
from argus_collector.delivery.transport import Transport
from argus_collector.delivery.uploads import Lane, Lanes
from argus_collector.runtime import contract as runtime
from argus_collector.storage import contract as storage

TICK_S = 0.5
EVENTS_TICK_S = 0.2  # a page's batch leaves 0.1-0.3 s after the page (owner 06.10.2026)
WIRE = "1.2"  # the events request schema (contract 3.1.0; heartbeat lists 1.1 and 1.2)
RUN_END = (api.ContactFreshnessEvent.type, api.JobFinishedEvent.type)  # after the snapshots


class Deliverer(Lanes):
    def __init__(
        self,
        db_path: Path | None,
        target: Callable[[], ApiTarget | None],
        hooks: DeliveryHooks,
        on_change: Callable[[], None] | None = None,
    ) -> None:
        self.db_path, self.target, self.hooks = db_path, target, hooks
        self.on_change = on_change or (lambda: None)
        self.error, self.failures, self.connected, self.pending = "", 0, False, 0
        self.server_error = 0  # the HTTP status of the last 5xx answer until a pass succeeds
        self._stop, self._wake, self._flush = threading.Event(), threading.Event(), False
        self._threads: list[threading.Thread] = []
        self._failing: tuple[Lane, ...] = ()  # the lanes whose error the panel shows
        self.event_holds, self.upload_holds = Holds(), Holds()  # runs refused as a whole
        self.transport = Transport()  # the one state of Lahetys, from heartbeat and delivery

    @property
    def state(self) -> str:
        return service.transport_state(self.error, self.pending, self.connected,
                                       self.transport.silent)

    def link(self, answered: bool) -> None:
        """Heartbeat outcome: no answer is `offline` also with an empty outbox; the
        first answer after an outage sends what is pending now, not after the backoff."""
        self.transport.heartbeat(answered)
        if answered and self.error == service.ERROR_OFFLINE:
            self.failures = 0
            self.flush()
        if self.transport.note(self.state, " (heartbeat)"):
            self.on_change()

    def start(self) -> None:
        """Both lanes running; a lane that ended is started again (the other keeps going)."""
        self._stop.clear()
        lanes = ((self._events, EVENTS_TICK_S, "delivery"), (self._uploads, TICK_S, "evidence"))
        alive = [t for t in self._threads if t.is_alive()]
        names = {t.name for t in alive}
        fresh = [threading.Thread(target=self._loop, args=(lane, tick), name=name, daemon=True)
                 for lane, tick, name in lanes if name not in names]
        self._threads = alive + fresh
        for thread in fresh:
            thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()

    def flush(self) -> None:
        """Send what is pending now instead of waiting for the 2 s window."""
        self._flush = True
        self._wake.set()

    def _loop(self, lane: Lane, tick_s: float) -> None:
        conn: sqlite3.Connection | None = None
        while not self._stop.is_set():
            try:
                conn = conn or storage.connect(self.db_path)
                delay = self.tick(conn, (lane,), tick_s)
            except Exception as exc:  # noqa: BLE001 - the thread never dies (06.10.2026)
                runtime.journal("delivery", f"pass failed, the outbox waits:"
                                f" {type(exc).__name__}: {str(exc)[:200]}")
                delay = service.MAX_BACKOFF_S
            self._wake.wait(delay)
            self._wake.clear()
        if conn is not None:
            conn.close()

    def tick(self, conn: sqlite3.Connection, lanes: tuple[Lane, ...] = (),
             tick_s: float = TICK_S) -> float:
        """One pass of the lanes (both: snapshots, then events); the delay before the next."""
        target, delay = self.target(), tick_s
        self.connected = target is not None  # paired
        run = lanes or (self._uploads, self._events)
        if target is not None:
            try:
                for lane in run:
                    lane(conn, target)
            except Failed as failed:
                delay, self._failing = self._failed(failed), run
            else:
                if self._failing in ((), run) or not lanes:  # only the failing lane clears it
                    self.error, self.failures, self.server_error, self._failing = "", 0, 0, ()
        if self.event_holds.refused() or self.upload_holds.refused():
            self.error = service.ERROR_PERMANENT  # Lähetys epäonnistui while a run waits
        self.pending = counters.totals(conn)[0]
        self.transport.note(self.state)
        self.on_change()
        return delay

    def _failed(self, failed: Failed) -> float:
        if failed.error == service.ERROR_LEASE:
            return TICK_S
        self.error = failed.error
        self.failures += 1
        return service.backoff_s(self.failures, failed.retry_after)

    def _events(self, conn: sqlite3.Connection, target: ApiTarget) -> None:
        flush, self._flush = self._flush, False
        for job_id, run_id in repo.pending_runs(conn):
            token = self.hooks.token_for(conn, job_id, run_id)
            if token is None or self.event_holds.held(run_id):
                continue
            rows, chunk = self._chunk(conn, job_id, run_id, flush)
            if not chunk:  # nothing new: ask the verdict of events kept evidence_pending
                rows = {r["event_id"]: r for r in repo.waiting_events(conn, run_id)}
                chunk = list(rows)
            if chunk:
                self._send(conn, target, (job_id, run_id, token), rows, chunk)

    def _chunk(self, conn: sqlite3.Connection, job_id: str, run_id: str, flush: bool
               ) -> tuple[dict[str, sqlite3.Row], list[str]]:
        """The run's next batch of new events (ids), [] while it is not ready."""
        rows = {r["event_id"]: r for r in repo.pending_events(conn, run_id, service.MAX_BATCH)}
        pending = [service.pending_from_row(dict(r)) for r in rows.values()]
        wanted = sorted({e for p in pending for e in p.evidence_ids})
        uploads = repo.upload_states(conn, wanted)
        hold = RUN_END if repo.pending_upload_ids(conn, run_id) else ()
        chunk = service.batch(pending, uploads, hold)
        if not chunk and pending:
            retry.lost(conn, self.hooks, job_id, rows[pending[0].event_id], uploads)
        ready = service.ready(chunk, datetime.now(UTC), flush)
        return rows, [p.event_id for p in chunk] if ready else []

    def _send(self, conn: sqlite3.Connection, target: ApiTarget, ids: tuple[str, str, str],
              rows: dict[str, sqlite3.Row], chunk: list[str]) -> None:
        job_id, run_id, token = ids
        events = [api.event_from_json(json.loads(rows[e]["event_json"])) for e in chunk]
        request = api.EventsRequest(schema_version=api.EventsRequestSchemaVersion(WIRE),
                                    execution_token=token, events=events)
        started = time.monotonic()
        try:
            resp = api.post_events(target.base_url, target.token, job_id, request,
                                   proxy_mode=target.api_mode, timeout_s=service.API_TIMEOUT_S)
        except api.ApiError as exc:
            kind, code = self._api_error(exc, job_id, run_id, token)
            if kind != service.ERROR_CONFLICT:  # the request refused: the run waits
                self.event_holds.hold(run_id, kind, exc.retry_after)
                return
            first = rows[chunk[0]]  # ARGUS keeps another event under this id
            repo.mark_events(conn, [(chunk[0], "rejected", code, None, None)])
            self.hooks.rejected(conn, job_id, str(first["type"]), code,
                                f"event {first['event_id']} seq {first['seq']}")
            return
        self.transport.answered()
        moved = results.apply(conn, self.hooks, job_id, rows, resp, service.elapsed_ms(started))
        if moved:
            self.event_holds.release(run_id)
        else:  # only sequence_gap or still evidence_pending: ask again after a backoff
            self.event_holds.hold(run_id, service.ERROR_RETRY)

