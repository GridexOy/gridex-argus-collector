"""What the collector answers to delivery and to the heartbeat loop.

Delivery asks for a run's execution token and reports lease problems,
rejections and applied batches; the heartbeat loop asks for the fields of
the next heartbeat and hands back the answer (lease renewals, commands).
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from argus_collector.api_client import contract as api
from argus_collector.delivery import contract as delivery
from argus_collector.runtime import contract as runtime
from argus_collector.scheduler import leases, runner, service
from argus_collector.scheduler import repository as repo
from argus_collector.storage import contract as storage
from argus_collector.walk import contract as walk


@dataclass(frozen=True)
class Settings:
    env: runner.WalkEnv
    stop_files: Callable[[], list[Path]]
    max_jobs: int = service.MAX_JOBS
    claim_interval_s: float = 10.0
    idle_wait_s: float = 2.0
    browser_free: Callable[[], bool] = lambda: True  # the owner's work browser is closed


class CollectorHooks:
    collecting: bool = False

    def __init__(
        self,
        settings: Settings,
        target: Callable[[], delivery.ApiTarget | None],
        on_change: Callable[[], None],
    ) -> None:
        self.settings, self.target, self.on_change = settings, target, on_change
        self.interrupts: dict[str, str] = {}
        self.lease_expiry: dict[str, datetime] = {}
        self.running_job: str | None = None
        self.claim_state, self.claim_error = "idle", ""
        self._reconcile_lock = threading.Lock()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = storage.connect(self.settings.env.db_path)
        try:
            yield conn
        finally:
            conn.close()

    @staticmethod
    def mode(target: delivery.ApiTarget) -> api.ProxyMode:
        return cast("api.ProxyMode", target.proxy_mode)

    def wake(self) -> None:
        """Wake the collecting thread (overridden by the collector)."""

    # Delivery hooks -----------------------------------------------------------------
    def token_for(self, conn: sqlite3.Connection, job_id: str, run_id: str) -> str | None:
        row = repo.job(conn, job_id)
        if row is None or row["run_id"] != run_id:
            return None
        return str(row["lease_token"])

    def lease_problem(self, job_id: str, run_id: str, code: str, token: str) -> None:
        """409 lease_* on `token`: reconcile, unless someone already got a new lease."""
        target = self.target()
        if target is None:
            return
        with self.connect() as conn:
            row = repo.job(conn, job_id)
            if row is not None and row["run_id"] == run_id and row["lease_token"] == token:
                self.reconcile_row(conn, target, row)

    def rejected(self, conn: sqlite3.Connection, job_id: str, kind: str, code: str) -> None:
        with conn:
            repo.bump_job_tx(conn, job_id, rejected=1)
            repo.update_job_tx(conn, job_id, last_reject_code=code)
        self.on_change()

    def applied(self, conn: sqlite3.Connection, job_id: str, resp: api.EventsResponse) -> None:
        """ARGUS's job state in every events answer: a pause or cancel takes effect after
        the current page, not only with the next heartbeat (owner 05.10.2026)."""
        state = resp.job_state.value
        if state == "cancelled":
            self.dispatch(conn, job_id, service.STOP_CANCEL)
        elif state == "paused" and job_id == self.running_job:
            runtime.journal("http", f"job {job_id}: paused in ARGUS (events answer)")
            self.dispatch(conn, job_id, service.STOP_PAUSE)

    # Heartbeat ----------------------------------------------------------------------
    def heartbeat_fields(self) -> leases.HeartbeatFields:
        with self.connect() as conn:
            return leases.heartbeat_fields(conn, self.collecting, self.settings.max_jobs)

    def apply_heartbeat(self, resp: api.HeartbeatResponse, sent_acks: list[str]) -> None:
        with self.connect() as conn:
            repo.mark_acks_sent(conn, sent_acks)
            for renewal in resp.leases:
                if renewal.status.value == "renewed" and renewal.lease_expires_at:
                    self.lease_expiry[renewal.job_id] = datetime.fromisoformat(
                        renewal.lease_expires_at
                    )
            interrupts = leases.apply_leases(conn, resp.leases)
            for cmd in resp.commands:
                found = leases.record_command(conn, cmd)
                if found is not None:
                    interrupts.append(found)
            for job_id, reason in interrupts:
                self.dispatch(conn, job_id, reason)
        self.on_change()

    def dispatch(self, conn: sqlite3.Connection, job_id: str, reason: str) -> None:
        """Apply an interrupt: to the running walk, or straight to an idle job."""
        if job_id == self.running_job and reason != leases.RESUME:
            self.interrupts.setdefault(job_id, reason)
            return
        row = repo.job(conn, job_id)
        if row is None or row["state"] in service.TERMINAL:
            return
        if reason == service.STOP_PAUSE:
            repo.update_job(conn, job_id, state=service.PAUSED)
        elif reason == leases.RESUME and row["state"] in (service.PAUSED,
                                                          service.NEEDS_ATTENTION):
            repo.update_job(conn, job_id, state=service.QUEUED)
            self.wake()
        elif reason == service.STOP_LEASE and row["state"] in service.RUNNABLE:
            repo.update_job(conn, job_id, state=service.WAITING_LEASE)
        elif reason == service.STOP_CANCEL:
            self._cancel_idle(conn, row)

    def _cancel_idle(self, conn: sqlite3.Connection, row: sqlite3.Row) -> None:
        if not row["started"]:
            repo.update_job(conn, row["job_id"], state=service.CANCELLED,
                            result_status=service.CANCELLED, completion_reason="manual_cancel")
            return
        saved = repo.checkpoint(conn, row["run_id"])
        cp = walk.WalkCheckpoint.from_json(saved) if saved else walk.WalkCheckpoint()
        runner.finish_run(conn, row, self.settings.env, cp, (walk.END_STOPPED, True))

    # Reconcile ----------------------------------------------------------------------
    def reconcile_waiting(self, conn: sqlite3.Connection, target: delivery.ApiTarget) -> None:
        for row in repo.jobs(conn, (service.WAITING_LEASE,)):
            self.reconcile_row(conn, target, row)

    def reconcile_row(
        self, conn: sqlite3.Connection, target: delivery.ApiTarget, row: sqlite3.Row
    ) -> str:
        with self._reconcile_lock:
            current = repo.job(conn, row["job_id"])
            if current is not None and current["lease_token"] != row["lease_token"]:
                return "resume" if not current["drain_only"] else "drain_only"
            mode, job_state = leases.reconcile(conn, target, row)
        fresh = repo.job(conn, row["job_id"])
        if fresh is not None:
            self.lease_expiry[row["job_id"]] = datetime.fromisoformat(fresh["lease_expires_at"])
        if mode == "drain_only" and job_state == "cancelled":
            self.dispatch(conn, row["job_id"], service.STOP_CANCEL)
        if mode == leases.RESUME:
            self.wake()
        self.on_change()
        return mode

    def now(self) -> datetime:
        return datetime.now(UTC)
