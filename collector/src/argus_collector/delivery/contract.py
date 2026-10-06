"""Single entry point of the `delivery` module: outbox, uploads, the delivery thread.

The scheduler writes events and snapshot uploads here inside its own write
transactions (`enqueue_event`, `enqueue_evidence` never commit), so an
observation and its outbox row are one transaction (TZ_SELAIN 10.2). The
`Deliverer` thread sends them at-least-once: snapshots first, then events of
each run in seq order, micro-batches of <= 50 events or 2 s (8.13); results
are stored per event; nothing is deleted.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from argus_collector.api_client import contract as api
from argus_collector.delivery import repository as repo
from argus_collector.delivery import service
from argus_collector.delivery.hooks import ApiTarget, DeliveryHooks
from argus_collector.delivery.loop import Deliverer

__all__ = [
    "SentEvent",
    "local_evidence_id",
    "run_results",
    "ApiTarget",
    "Deliverer",
    "DeliveryHooks",
    "DeliveryStats",
    "MakeEvent",
    "ReconcileInfo",
    "Rejection",
    "enqueue_event",
    "enqueue_evidence",
    "error_text",
    "job_totals",
    "next_seq",
    "reconcile_info",
    "reason",
    "rejections",
    "run_events",
    "run_ids",
    "stats",
]

MakeEvent = Callable[[str, int, str], api.Event]  # (event_id, seq, occurred_at) -> event
P95_WINDOW_S = 60
API_TIMEOUT_S = service.API_TIMEOUT_S  # every ARGUS call of the collector waits 30 s


@dataclass(frozen=True)
class DeliveryStats:
    pending: int  # events + snapshots not yet answered by ARGUS
    errors: int  # events + snapshots ARGUS rejected
    p95_s: float | None  # delivery time of events queued and acknowledged in the last minute
    last_code: str = ""  # code of the latest rejection (words: `reason`, fi.json)


@dataclass(frozen=True)
class ReconcileInfo:
    last_acknowledged_seq: int
    pending_event_ids: list[str]
    pending_evidence_ids: list[str]


def next_seq(conn: sqlite3.Connection, run_id: str) -> int:
    """Next seq of a run: monotonic, never reset by a restart (it lives in the outbox)."""
    return repo.next_seq(conn, run_id)


def enqueue_event(
    conn: sqlite3.Connection,
    job_id: str,
    run_id: str,
    make: MakeEvent,
    evidence_ids: list[str],
    seq: int | None = None,
) -> tuple[str, int]:
    """Add one event to the outbox inside the caller's transaction; (event_id, seq)."""
    number = seq if seq is not None else repo.next_seq(conn, run_id)
    event_id = str(uuid.uuid4())
    event = make(event_id, number, datetime.now(UTC).isoformat(timespec="milliseconds"))
    data = api.to_json(event)
    repo.insert_event(conn, (event_id, job_id, run_id, number), str(data["type"]), data,
                      evidence_ids)
    return event_id, number


def enqueue_evidence(
    conn: sqlite3.Connection, local_evidence_id: str, metadata: api.EvidenceMetadata
) -> bool:
    """Queue the upload of a stored snapshot; False when it is already queued."""
    ids = (metadata.evidence_id, metadata.job_id, metadata.run_id, local_evidence_id)
    return repo.insert_upload(conn, ids, api.to_json(metadata))


def stats(conn: sqlite3.Connection) -> DeliveryStats:
    pending, errors = repo.totals(conn)
    since = (datetime.now(UTC) - timedelta(seconds=P95_WINDOW_S)).isoformat(
        timespec="milliseconds"
    )
    last = repo.rejected_rows(conn)[:1]
    return DeliveryStats(pending, errors, service.p95_s(repo.acked_since(conn, since)),
                         str(last[0]["code"]) if last else "")


@dataclass(frozen=True)
class Rejection:
    job_id: str
    kind: str  # event type or `evidence`
    item_id: str  # event_id or evidence_id
    seq: int | None
    code: str
    at: str


def rejections(conn: sqlite3.Connection) -> list[Rejection]:
    """Every rejected event and snapshot, the latest first."""
    return [Rejection(str(r["job_id"]), str(r["kind"]), str(r["item_id"]), r["seq"],
                      str(r["code"]), str(r["at"] or "")) for r in repo.rejected_rows(conn)]


def reason(code: str) -> str:
    """English words for a rejection code (journal, `pilot rejected`)."""
    return service.reason(code)


def unsent_runs(conn: sqlite3.Connection) -> set[str]:
    """Runs with events still to send: their lease is renewed until the tail is out."""
    return {run_id for _, run_id in repo.pending_runs(conn)}


def job_totals(conn: sqlite3.Connection, job_id: str) -> tuple[int, int]:
    """(pending, rejected) events + snapshots of one job."""
    return repo.totals(conn, job_id)


def reconcile_info(conn: sqlite3.Connection, run_id: str) -> ReconcileInfo:
    rows = repo.run_rows(conn, run_id)
    acked = 0
    for row in rows:
        if row["status"] not in repo.DONE or int(row["seq"]) != acked + 1:
            break
        acked = int(row["seq"])
    pending = [str(r["event_id"]) for r in rows if r["status"] == "pending"]
    return ReconcileInfo(acked, pending, repo.pending_upload_ids(conn, run_id))


def run_events(conn: sqlite3.Connection, run_id: str, event_type: str) -> list[dict[str, object]]:
    """Payloads of the run's events of one type (e.g. model.called for job.finished)."""
    out: list[dict[str, object]] = []
    for row in repo.run_rows(conn, run_id):
        if row["type"] == event_type:
            payload = json.loads(row["event_json"]).get("payload", {})
            out.append(payload if isinstance(payload, dict) else {})
    return out


@dataclass(frozen=True)
class SentEvent:
    """One outbox event of a run with what ARGUS answered (for reports)."""

    type: str
    payload: dict[str, object]
    status: str  # pending | accepted | duplicate | rejected
    channel_status: str | None  # the strongest K3 status ARGUS gave a contact event


def run_results(conn: sqlite3.Connection, run_id: str) -> list[SentEvent]:
    out = []
    for row in repo.run_rows(conn, run_id):
        payload = json.loads(row["event_json"]).get("payload", {})
        out.append(SentEvent(str(row["type"]), payload if isinstance(payload, dict) else {},
                             str(row["status"]), row["channel_status"]))
    return out


def local_evidence_id(conn: sqlite3.Connection, evidence_id: str) -> str | None:
    """The local snapshot id behind an evidence id sent to ARGUS."""
    return repo.local_evidence_id(conn, evidence_id)


def run_ids(conn: sqlite3.Connection, job_id: str) -> list[str]:
    return repo.job_run_ids(conn, job_id)


def error_text(exc: api.ApiError) -> str:
    """`<code> (<words>) request_id=<id>` of a failed request, for the journal; ARGUS's
    detail is left out (it may quote a contact value)."""
    body = exc.error
    code = body.code if body else service.status_code(exc.status) if exc.status else "offline"
    rid = f" request_id={body.request_id}" if body and body.request_id else ""
    return f"{code} ({service.reason(code)}){rid}"
