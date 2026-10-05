"""Claims, leases, heartbeat fields, ARGUS commands and reconcile (TZ_SELAIN 8.14).

A claimed job is stored locally with its whole ClaimedJob document and the
current lease; the same run claimed again only renews the lease (run_id and
seq stay), a new run of a known job resets the run fields. Commands arrive
in the heartbeat answer, are recorded once and acknowledged in the next
heartbeat (a repeated command is acknowledged `already_applied`).
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import cast

from argus_collector.api_client import contract as api
from argus_collector.delivery import contract as delivery
from argus_collector.runtime import contract as runtime
from argus_collector.scheduler import repository as repo
from argus_collector.scheduler import service
from argus_collector.storage import contract as storage

RESUME = "resume"


@dataclass(frozen=True)
class HeartbeatFields:
    collecting: bool
    active_jobs: list[api.ActiveLease]
    outbox_pending: int
    free_job_slots: int
    acknowledgements: list[api.CommandAck]


def _lease_fields(lease: api.Lease) -> dict[str, object]:
    return {"lease_token": lease.execution_token, "lease_generation": lease.lease_generation,
            "lease_expires_at": lease.lease_expires_at}


def store_claimed(conn: sqlite3.Connection, claimed: api.ClaimedJob) -> str:
    """Insert or update the local job; returns new | renewed | new_run."""
    job, lease = claimed.job, claimed.lease
    definition = json.dumps(api.to_json(claimed), ensure_ascii=False)
    row = repo.job(conn, job.job_id)
    with storage.transaction(conn):
        if row is None:
            repo.insert_job_tx(conn, {
                "job_id": job.job_id, "batch_id": job.batch_id, "company_id": job.company_id,
                "company_name": job.company_name, "definition_json": definition,
                "state": service.QUEUED, "stage": service.STAGE_QUEUED, "run_id": lease.run_id,
                "lease_token": lease.execution_token, "lease_generation": lease.lease_generation,
                "lease_expires_at": lease.lease_expires_at})
            return "new"
        if row["run_id"] == lease.run_id:
            state = service.QUEUED if row["state"] == service.WAITING_LEASE else row["state"]
            repo.update_job_tx(conn, job.job_id, definition_json=definition, drain_only=0,
                               state=state, **_lease_fields(lease))
            return "renewed"
        repo.update_job_tx(
            conn, job.job_id, definition_json=definition, run_id=lease.run_id, drain_only=0,
            state=service.QUEUED, stage=service.STAGE_QUEUED, started=0, finished=0,
            result_status="", completion_reason="", detail="", claimed_at=repo.now_iso(),
            **_lease_fields(lease),
        )
        return "new_run"


def heartbeat_fields(conn: sqlite3.Connection, collecting: bool, max_jobs: int) -> HeartbeatFields:
    active = repo.jobs(conn, service.ACTIVE)
    leases = [
        api.ActiveLease(job_id=r["job_id"], run_id=r["run_id"], execution_token=r["lease_token"],
                        lease_generation=int(r["lease_generation"]))
        for r in active
        if not r["drain_only"]
    ]
    acks = [
        api.CommandAck(command_id=r["command_id"], status=api.CommandAckStatus(r["status"]),
                       detail=r["detail"])
        for r in repo.unsent_acks(conn)
    ]
    pending = delivery.stats(conn).pending
    return HeartbeatFields(collecting, leases, pending, service.free_slots(len(active), max_jobs),
                           acks)


def apply_leases(
    conn: sqlite3.Connection, renewals: list[api.LeaseRenewal]
) -> list[tuple[str, str]]:
    """Renewed leases get their new expiry; the rest become interrupts (job, reason)."""
    out: list[tuple[str, str]] = []
    for renewal in renewals:
        status = renewal.status.value
        if status == "renewed" and renewal.lease_expires_at:
            repo.update_job(conn, renewal.job_id, lease_expires_at=renewal.lease_expires_at)
        elif status == "cancelled":
            out.append((renewal.job_id, service.STOP_CANCEL))
        elif status in ("expired", "mismatch"):
            out.append((renewal.job_id, service.STOP_LEASE))
    return out


def record_command(conn: sqlite3.Connection, cmd: api.Command) -> tuple[str, str] | None:
    """Record one command; returns the interrupt to apply, None when nothing to do."""
    if repo.command(conn, cmd.command_id) is not None:
        repo.resend_ack(conn, cmd.command_id)
        return None
    action, row = cmd.action.value, repo.job(conn, cmd.job_id)
    head = (cmd.command_id, cmd.job_id, action, cmd.state_revision)
    runtime.journal("http", f"command {action} for job {cmd.job_id}")
    if row is None:
        repo.insert_command(conn, (*head, "failed", "unknown job"))
        return None
    if action == "continue":
        repo.insert_command(conn, (*head, "applied", "the next claim starts the new run"))
        return None
    if row["state"] in service.TERMINAL:
        status = "already_applied" if action == "cancel" else "failed"
        repo.insert_command(conn, (*head, status, f"job is {row['state']}"))
        return None
    repo.insert_command(conn, (*head, "applied", ""))
    reasons = {"pause": service.STOP_PAUSE, "cancel": service.STOP_CANCEL, "resume": RESUME}
    return cmd.job_id, reasons[action]


def reconcile(
    conn: sqlite3.Connection, target: delivery.ApiTarget, row: sqlite3.Row
) -> tuple[str, str]:
    """(mode resume | drain_only | offline | lost, ARGUS job_state or code)."""
    info = delivery.reconcile_info(conn, row["run_id"])
    request = api.ReconcileRequest(
        worker_id=target.worker_id, run_id=row["run_id"],
        last_acknowledged_seq=info.last_acknowledged_seq,
        pending_event_ids=info.pending_event_ids, pending_evidence_ids=info.pending_evidence_ids,
    )
    mode = cast("api.ProxyMode", target.proxy_mode)
    try:
        resp = api.reconcile_job(target.base_url, target.token, row["job_id"], request,
                                 proxy_mode=mode)
    except api.ApiError as exc:
        code = exc.error.code if exc.error else ""
        runtime.journal("http", f"reconcile job {row['job_id']}: HTTP {exc.status}"
                        f" {delivery.error_text(exc)}")
        if exc.status == 0 or exc.status >= 500 or exc.status in (401, 403, 429):
            return "offline", code
        repo.update_job(conn, row["job_id"], state=service.FAILED, detail=f"lease lost: {code}")
        return "lost", code
    drain = resp.mode.value != RESUME
    fields = {**_lease_fields(resp.lease), "drain_only": 1 if drain else 0}
    if not drain and row["state"] in (service.WAITING_LEASE, service.RUNNING):
        fields["state"] = service.QUEUED
    repo.update_job(conn, row["job_id"], **fields)
    runtime.journal("http", f"reconcile job {row['job_id']}: {resp.mode.value},"
                    f" job_state={resp.job_state.value}, last_seq={resp.last_contiguous_seq}")
    return resp.mode.value, resp.job_state.value
