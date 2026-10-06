"""The collector: Kaynnista / Pysayta, the collecting thread, heartbeat answers.

One thread walks one job at a time (TZ_SELAIN 8.13) in one Chrome for the whole
collection, a fresh context per company (owner 06.10.2026), and claims new jobs;
delivery runs on its own thread. Pysayta and STOP stop walking and claiming, the
outbox keeps going (TZ_TANDEM A3.3); after a restart an interrupted walk resumes.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime

from argus_collector.api_client import contract as api
from argus_collector.browser import contract as browser
from argus_collector.delivery import contract as delivery
from argus_collector.runtime import contract as runtime
from argus_collector.scheduler import leases, runner, service, views
from argus_collector.scheduler import repository as repo
from argus_collector.scheduler.hooks import CollectorHooks, Settings
from argus_collector.storage import contract as storage
from argus_collector.walk import contract as walk


class Collector(CollectorHooks):
    def __init__(
        self,
        settings: Settings,
        target: Callable[[], delivery.ApiTarget | None],
        capabilities: Callable[[], api.Capabilities],
        on_change: Callable[[], None],
        on_walk_event: Callable[[walk.WalkEvent], None],
    ) -> None:
        super().__init__(settings, target, on_change)
        self.capabilities, self.on_walk_event = capabilities, on_walk_event
        self.collecting = False
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None
        self._host = browser.BrowserHost(settings.env.headless, settings.env.profile_dir)
        self.deliverer = delivery.Deliverer(settings.env.db_path, target, self, on_change)
        with self.connect() as conn:
            for row in repo.jobs(conn, (service.RUNNING,)):
                repo.update_job(conn, row["job_id"], state=service.STOPPED)

    @property
    def walking(self) -> bool:
        return self.running_job is not None

    def start(self) -> None:
        """Kaynnista: collect (claim + walk) until Pysayta or STOP."""
        if self.collecting:
            return
        self.collecting = True
        runtime.journal("http", "collecting on")
        self._thread = threading.Thread(target=self._loop, name="collector", daemon=True)
        self._thread.start()
        self.on_change()

    def stop(self, wait_s: float = 0.0) -> None:
        """Pysayta: stop at the next step, claim nothing; `wait_s`: wait for Chrome to close."""
        if self.collecting:
            runtime.journal("http", "collecting off")
        self.collecting = False
        self._wake.set()
        self.on_change()
        if wait_s and self._thread is not None:
            self._thread.join(wait_s)

    def wake(self) -> None:
        self._wake.set()

    def apply_heartbeat(self, resp: api.HeartbeatResponse, sent_acks: list[str]) -> None:
        self.deliverer.link(True)
        super().apply_heartbeat(resp, sent_acks)

    def attention_done(self, job_id: str) -> None:
        """Jatka kasin tehdyn toimen jalkeen: the job walks again from where it stopped."""
        with self.connect() as conn:
            row = repo.job(conn, job_id)
            if row is not None and row["state"] == service.NEEDS_ATTENTION:
                repo.update_job(conn, job_id, state=service.QUEUED, detail="")
                runtime.journal("browser", f"job {job_id}: attention solved by the owner")
        self.wake()
        self.on_change()

    def heartbeat_failed(self, status: int) -> None:
        """Status 0 (no answer): Lahetys `offline` once delivery got none either."""
        self.deliverer.link(status != 0)

    def _stopped(self) -> bool:
        if self.settings.stop_files():
            if self.collecting:
                runtime.journal("http", "STOP file found: collecting off")
            self.collecting = False
        return not self.collecting

    def _loop(self) -> None:
        conn = storage.connect(self.settings.env.db_path)
        self._host = browser.BrowserHost(self.settings.env.headless, self.settings.env.profile_dir)
        last_claim = 0.0
        try:
            while not self._stopped():
                target = self.target()
                free = self.settings.browser_free()
                row = self._next_runnable(conn) if target is not None and free else None
                if row is not None:
                    self._run(conn, row)
                    continue
                if target is not None:
                    self.reconcile_waiting(conn, target)
                    if time.monotonic() - last_claim >= self.settings.claim_interval_s:
                        last_claim = time.monotonic()
                        if self._claim(conn, target):
                            continue
                self._wake.wait(self.settings.idle_wait_s)
                self._wake.clear()
        finally:
            self._host.close()
            runtime.journal("browser", f"chrome closed: {self._host.starts} starts,"
                            f" {self._host.start_ms} ms")
            conn.close()
            self.on_change()

    def _next_runnable(self, conn: sqlite3.Connection) -> sqlite3.Row | None:
        now = datetime.now(UTC)
        for row in repo.jobs(conn, service.RUNNABLE):
            if datetime.fromisoformat(row["lease_expires_at"]) <= now:
                repo.update_job(conn, row["job_id"], state=service.WAITING_LEASE)
                continue
            return row
        return None

    def _claim(self, conn: sqlite3.Connection, target: delivery.ApiTarget) -> int:
        active = len(repo.jobs(conn, service.ACTIVE))
        free = service.free_slots(active, self.settings.max_jobs)
        if free == 0:
            return 0
        self.claim_state = "loading" if active == 0 else self.claim_state
        self.on_change()
        request = api.ClaimRequest(worker_id=target.worker_id, max_jobs=free,
                                   capabilities=self.capabilities())
        try:
            resp = api.claim_jobs(target.base_url, target.token, request,
                                  proxy_mode=self.mode(target), timeout_s=delivery.API_TIMEOUT_S)
        except api.ApiError as exc:
            self.claim_state, self.claim_error = "failed", str(exc)
            runtime.journal("http", f"claim: HTTP {exc.status} {delivery.error_text(exc)}")
            self.on_change()
            return 0
        for claimed in resp.jobs:
            kind = leases.store_claimed(conn, claimed)
            runtime.journal("http", f"claim: job {claimed.job.job_id} {kind}"
                            f" run {claimed.lease.run_id} gen {claimed.lease.lease_generation}")
        self.claim_state, self.claim_error = "done", ""
        self.on_change()
        return len(resp.jobs)

    def _should_stop(self, job_id: str) -> Callable[[], bool]:
        def check() -> bool:
            if self._stopped() or job_id in self.interrupts:
                return True
            row_expiry = self.lease_expiry.get(job_id)
            if row_expiry is not None and row_expiry <= datetime.now(UTC):
                self.interrupts.setdefault(job_id, service.STOP_LEASE)
                return True
            return False

        return check

    def _run(self, conn: sqlite3.Connection, row: sqlite3.Row) -> None:
        job_id = row["job_id"]
        self.running_job = job_id
        self.lease_expiry[job_id] = datetime.fromisoformat(row["lease_expires_at"])
        self.on_change()
        hooks = (self._should_stop(job_id), self.on_walk_event, lambda: self.deliverer.state)
        try:
            state = runner.run_job(conn, row, (self.settings.env, self._host), hooks,
                                   lambda: self.interrupts.pop(job_id, None))
            runtime.journal("browser", f"job {job_id}: walk ended, job {state}")
        finally:
            self.running_job = None
            self.deliverer.flush()
            self.on_change()

    def queue_view(self) -> views.QueueView:
        with self.connect() as conn:
            claim = (self.claim_state, self.claim_error)
            return views.queue_view(conn, self.running_job, claim, self.collecting)

    def attention_view(self) -> list[views.AttentionItem]:
        with self.connect() as conn:
            return views.attention_view(conn)

    def delivery_view(self) -> views.DeliveryView:
        with self.connect() as conn:
            return views.delivery_view(conn, self.deliverer.state,
                                       self.deliverer.server_error)
