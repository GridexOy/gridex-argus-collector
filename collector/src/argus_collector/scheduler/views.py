"""What the panel shows of the queue and of delivery: local SQLite + last answers."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from argus_collector.delivery import contract as delivery
from argus_collector.scheduler import repository as repo
from argus_collector.scheduler import runner, service

RECENT_HOURS = 24


@dataclass(frozen=True)
class QueueRow:
    job_id: str
    company: str
    state: str  # local state (scheduler.service)
    stage: str  # queued | browser | finalizing | "" (done and delivered)
    persons: int
    channels: int
    sources: int
    rejected: int
    reject_code: str
    completion_reason: str
    detail: str


@dataclass(frozen=True)
class QueueView:
    rows: list[QueueRow]
    claim_state: str  # idle | loading | failed | done
    claim_error: str
    collecting: bool


@dataclass(frozen=True)
class DeliveryView:
    pending: int
    errors: int
    p95_s: float | None
    state: str  # TransportState
    last_code: str = ""  # code of the latest rejection
    server_error: int = 0  # HTTP status of the last 5xx answer while it lasts
    expired: int = 0  # events and snapshots given up as `Vanhentunut` (0.4.8.11)


def _stage(row: sqlite3.Row, pending: int, running: bool) -> str:
    if running:
        return service.STAGE_BROWSER
    if row["state"] in service.TERMINAL:
        return service.STAGE_FINALIZING if pending else ""
    return service.STAGE_QUEUED


def queue_view(
    conn: sqlite3.Connection, running_job: str | None, claim: tuple[str, str], collecting: bool
) -> QueueView:
    """Active jobs plus the ones that changed in the last 24 h, in claim order."""
    since = (datetime.now(UTC) - timedelta(hours=RECENT_HOURS)).isoformat(timespec="milliseconds")
    recent = list(repo.recent_jobs(conn, since, service.ACTIVE))
    waiting = delivery.pending_by_job(conn, [str(row["job_id"]) for row in recent])
    rows = []
    for row in recent:
        pending = waiting.get(str(row["job_id"]), 0)
        rows.append(QueueRow(
            row["job_id"], row["company_name"], row["state"],
            _stage(row, pending, row["job_id"] == running_job),
            int(row["persons"]), int(row["channels"]), int(row["sources"]),
            int(row["rejected"]), row["last_reject_code"], row["completion_reason"], row["detail"],
        ))
    return QueueView(rows, claim[0], claim[1], collecting)


@dataclass(frozen=True)
class AttentionItem:
    """A job waiting for the owner (Huomio): the URL of the bot check to pass."""

    job_id: str
    company: str
    url: str
    reason: str  # a Gap.reason (captcha)


def attention_view(conn: sqlite3.Connection) -> list[AttentionItem]:
    return [
        AttentionItem(row["job_id"], row["company_name"], row["detail"], "captcha")
        for row in repo.jobs(conn, (service.NEEDS_ATTENTION,))
    ]


def delivery_view(conn: sqlite3.Connection, transport_state: str,
                  server_error: int = 0) -> DeliveryView:
    stats = delivery.stats(conn)
    return DeliveryView(stats.pending, stats.errors, stats.p95_s, transport_state,
                        stats.last_code, server_error, stats.expired)


@dataclass(frozen=True)
class JobFacts:
    """A job as a report sees it (pilot): identity, result, hosts, its runs."""

    job_id: str
    batch_id: str
    company: str
    state: str
    completion_reason: str
    persons: int
    channels: int
    approved_hosts: tuple[str, ...]
    run_ids: tuple[str, ...]


def job_facts(conn: sqlite3.Connection, batch_id: str | None) -> list[JobFacts]:
    """Jobs of one batch (the latest claimed batch when None), in claim order."""
    rows = repo.jobs(conn)
    if batch_id is None and rows:
        batch_id = max(rows, key=lambda r: str(r["claimed_at"]))["batch_id"]
    out = []
    for row in rows:
        if row["batch_id"] != batch_id:
            continue
        claimed = runner.claimed_job(row)
        hosts = tuple(runner.host_key(h.host) for h in claimed.job.scope.approved_hosts)
        out.append(JobFacts(
            row["job_id"], row["batch_id"], row["company_name"], row["state"],
            row["completion_reason"], int(row["persons"]), int(row["channels"]), hosts,
            tuple(delivery.run_ids(conn, row["job_id"])),
        ))
    return out


def job_companies(conn: sqlite3.Connection) -> dict[str, str]:
    """job_id -> company name of every job claimed on this PC (timing report)."""
    return {str(row["job_id"]): str(row["company_name"]) for row in repo.jobs(conn)}
