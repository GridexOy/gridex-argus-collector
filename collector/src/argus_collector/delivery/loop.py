"""The delivery thread: snapshots first, then events in seq order, results back.

Independent of the walk (TZ_SELAIN 8.1 p.4): it runs while a connection is
saved, also after Pysayta or a STOP file, until the outbox is empty.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from argus_collector.api_client import contract as api
from argus_collector.delivery import repository as repo
from argus_collector.delivery import results, service
from argus_collector.delivery.hooks import ApiTarget, DeliveryHooks, Failed
from argus_collector.evidence import contract as evidence
from argus_collector.runtime import contract as runtime
from argus_collector.storage import contract as storage

TICK_S = 0.5
UPLOADS_PER_TICK = 20
HTML_MIME = "text/html; charset=utf-8"


class Deliverer:
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
        self.link_down = False  # the last heartbeat got no answer at all
        self._stop, self._wake, self._flush = threading.Event(), threading.Event(), False
        self._thread: threading.Thread | None = None

    @property
    def state(self) -> str:
        connected = self.connected and not self.link_down
        return service.transport_state(self.error, self.pending, connected)

    def link(self, answered: bool) -> None:
        """Heartbeat outcome: no answer is `offline` also with an empty outbox; the
        first answer after an outage sends what is pending now, not after the backoff."""
        before, self.link_down = self.state, not answered
        if answered and self.error == service.ERROR_OFFLINE:
            self.failures = 0
            self.flush()
        if self.state != before:
            runtime.journal("delivery", f"transport {before} -> {self.state} (heartbeat)")
            self.on_change()

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="delivery", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()

    def flush(self) -> None:
        """Send what is pending now instead of waiting for the 2 s window."""
        self._flush = True
        self._wake.set()

    def _loop(self) -> None:
        conn = storage.connect(self.db_path)
        try:
            while not self._stop.is_set():
                delay = self.tick(conn)
                self._wake.wait(delay)
                self._wake.clear()
        finally:
            conn.close()

    def tick(self, conn: sqlite3.Connection) -> float:
        """One pass; returns the delay before the next one."""
        before, target = self.state, self.target()
        delay = TICK_S
        if target is None:
            self.connected = False
        else:
            try:
                self._uploads(conn, target)
                self._events(conn, target)
                self.error, self.failures, self.connected = "", 0, True
            except Failed as failed:
                delay = self._failed(failed)
        self.pending = repo.totals(conn)[0]
        if self.state != before:
            runtime.journal("delivery", f"transport {before} -> {self.state}")
        self.on_change()
        return delay

    def _failed(self, failed: Failed) -> float:
        if failed.error == service.ERROR_LEASE:
            return TICK_S
        self.error, self.connected = failed.error, failed.error != service.ERROR_OFFLINE
        self.failures += 1
        return service.backoff_s(self.failures, failed.retry_after)

    def _api_error(self, exc: api.ApiError, job_id: str, run_id: str, token: str) -> str:
        """Class of an error; raises Failed for the classes that stop this pass."""
        code = exc.error.code if exc.error is not None else ""
        retryable = exc.error.retryable if exc.error is not None else False
        kind = service.classify(exc.status, code, retryable)
        runtime.journal("delivery", f"job {job_id}: HTTP {exc.status} {code or kind}")
        self.link_down = self.link_down and exc.status == 0
        if kind == service.ERROR_LEASE:
            self.hooks.lease_problem(job_id, run_id, code, token)
        if kind in (service.ERROR_PERMANENT, service.ERROR_CONFLICT):
            return code or kind
        raise Failed(kind, exc.retry_after)

    def _uploads(self, conn: sqlite3.Connection, target: ApiTarget) -> None:
        for row in repo.pending_uploads(conn, UPLOADS_PER_TICK):
            job_id, run_id, evidence_id = row["job_id"], row["run_id"], row["evidence_id"]
            token = self.hooks.token_for(conn, job_id, run_id)
            if token is None:
                continue
            snap = evidence.load_snapshot(conn, row["local_evidence_id"])
            if snap is None:
                self._reject_upload(conn, job_id, evidence_id, "evidence_missing")
                continue
            metadata = api.from_json(api.EvidenceMetadata, json.loads(row["metadata_json"]))
            try:
                resp = api.upload_evidence(
                    target.base_url, target.token, job_id, token, metadata, snap.html,
                    file_content_type=HTML_MIME, proxy_mode=_mode(target),
                )
            except api.ApiError as exc:
                code = self._api_error(exc, job_id, run_id, token)
                self._reject_upload(conn, job_id, evidence_id, code)
                continue
            self.link_down = False
            repo.mark_upload(conn, evidence_id, resp.status.value, "")

    def _reject_upload(
        self, conn: sqlite3.Connection, job_id: str, evidence_id: str, code: str
    ) -> None:
        repo.mark_upload(conn, evidence_id, "rejected", code)
        self.hooks.rejected(conn, job_id, "evidence", code)

    def _events(self, conn: sqlite3.Connection, target: ApiTarget) -> None:
        flush, self._flush = self._flush, False
        for job_id, run_id in repo.pending_runs(conn):
            token = self.hooks.token_for(conn, job_id, run_id)
            if token is None:
                continue
            rows = {r["event_id"]: r for r in repo.pending_events(conn, run_id, service.MAX_BATCH)}
            pending = [service.pending_from_row(dict(r)) for r in rows.values()]
            wanted = sorted({e for p in pending for e in p.evidence_ids})
            chunk = service.batch(pending, repo.upload_states(conn, wanted))
            if not service.ready(chunk, datetime.now(UTC), flush):
                continue
            events = [api.event_from_json(json.loads(rows[p.event_id]["event_json"]))
                      for p in chunk]
            request = api.EventsRequest(execution_token=token, events=events)
            try:
                resp = api.post_events(
                    target.base_url, target.token, job_id, request, proxy_mode=_mode(target)
                )
            except api.ApiError as exc:
                code = self._api_error(exc, job_id, run_id, token)
                repo.mark_events(conn, [(chunk[0].event_id, "rejected", code, None, None)])
                continue
            self.link_down = False
            results.apply(conn, self.hooks, job_id, rows, resp)


def _mode(target: ApiTarget) -> api.ProxyMode:
    return cast("api.ProxyMode", target.proxy_mode)
