"""Runs that are no longer their job's current run (owner 06.10.2026, outbox defect).

ARGUS may hand a job out again with a new run (a lease that ran out while it answered
500 / 502). What the old run still has in the outbox keeps its run: its token is kept
here when the new run is stored (`keep_tx`), its events and snapshots go with it, and
the 409 the expired token gets is reconciled for that run - ARGUS answers with a
drain-only token (late observations of an old run, TZ_SELAIN 8.14), kept here too.
Nothing of an old run leaves the outbox unsent.
"""

from __future__ import annotations

import sqlite3
from typing import cast

from argus_collector.api_client import contract as api
from argus_collector.delivery import contract as delivery
from argus_collector.runtime import contract as runtime
from argus_collector.scheduler.repository import now_iso


def keep_tx(conn: sqlite3.Connection, row: sqlite3.Row) -> None:
    """Inside the caller's transaction: the job's run before a new one replaces it."""
    conn.execute(
        "INSERT OR IGNORE INTO run_tokens (run_id, job_id, lease_token, drain_only, updated_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (row["run_id"], row["job_id"], row["lease_token"], int(row["drain_only"]), now_iso()),
    )


def token(conn: sqlite3.Connection, run_id: str) -> str | None:
    found = conn.execute("SELECT lease_token FROM run_tokens WHERE run_id = ?",
                         (run_id,)).fetchone()
    return str(found[0]) if found else None


def reconcile(conn: sqlite3.Connection, target: delivery.ApiTarget, job_id: str,
              run_id: str) -> str:
    """resume | drain_only (the run's new token kept) | offline | lost (it stays pending)."""
    info = delivery.reconcile_info(conn, run_id)
    request = api.ReconcileRequest(
        worker_id=target.worker_id, run_id=run_id,
        last_acknowledged_seq=info.last_acknowledged_seq,
        pending_event_ids=info.pending_event_ids, pending_evidence_ids=info.pending_evidence_ids,
    )
    try:
        resp = api.reconcile_job(target.base_url, target.token, job_id, request,
                                 proxy_mode=cast("api.ProxyMode", target.proxy_mode),
                                 timeout_s=delivery.API_TIMEOUT_S)
    except api.ApiError as exc:
        runtime.journal("http", f"reconcile old run {run_id} of job {job_id}: HTTP {exc.status}"
                        f" {delivery.error_text(exc)}; its outbox stays pending")
        return "offline" if exc.status == 0 or exc.status >= 500 else "lost"
    mode = resp.mode.value
    with conn:
        conn.execute("UPDATE run_tokens SET lease_token = ?, drain_only = ?, updated_at = ?"
                     " WHERE run_id = ?", (resp.lease.execution_token,
                                           int(mode != "resume"), now_iso(), run_id))
    runtime.journal("http", f"reconcile old run {run_id} of job {job_id}: {mode},"
                    f" last_seq={resp.last_contiguous_seq}")
    return mode
