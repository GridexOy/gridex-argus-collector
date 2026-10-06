"""Pure rules of delivery: micro-batches, error classes, backoff, p95, state."""

from __future__ import annotations

import json
import math
import random
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

MAX_BATCH = 50  # events per request (TZ_SELAIN 8.13)
MAX_WAIT_S = 2.0  # a micro-batch leaves at 50 events or after 2 s
MAX_BACKOFF_S = 30.0
API_TIMEOUT_S = 30.0  # claim, events, reconcile as heartbeat and uploads (WINLOG 06.10: 10 s)
CLOSING = ("source.processed", "source.blocked")  # a page's last event (a run end: flush)

STATE_ONLINE = "online"
STATE_OFFLINE = "offline"
STATE_SYNCING = "syncing"
STATE_SYNCED = "synced"
STATE_ERROR = "delivery_error"

ERROR_OFFLINE = "offline"  # no answer at all (status 0)
ERROR_AUTH = "auth"  # 401 / 403: token rejected or revoked
ERROR_LEASE = "lease"  # 409 lease_expired / lease_mismatch / job_cancelled -> reconcile
ERROR_RATE = "rate"  # 429
ERROR_CONFLICT = "conflict"  # 409 idempotency_conflict
ERROR_PERMANENT = "permanent"  # 4xx the same request will never pass
ERROR_RETRY = "retry"  # 5xx or retryable=true
LEASE_CODES = ("lease_expired", "lease_mismatch", "job_cancelled")
FILE_CODES = ("payload_too_large", "evidence_hash_mismatch")  # the snapshot itself is refused
REASONS = {  # what an ARGUS code means, for the journal (the panel's words are in fi.json)
    "person_without_name": "a person event without the person's name",  # rules of 3.1.0
    "no_channel": "nothing to record: no channel and no person",
    "channel_value_unreadable": "the channel value cannot be read",
    "snapshot_missing": "the snapshot is missing in ARGUS",
    "quote_not_found": "the quote is not in the snapshot",
    "value_not_in_quote": "the value is not in its quote",
    "job_mismatch": "the event names another job",
    "host_not_approved": "the host is not approved for this job",
    "evidence_missing": "the snapshot is missing in ARGUS",
    "evidence_hash_mismatch": "the quote is not in the snapshot",
    "field_audit_missing": "the field audit is missing",
    "invalid_input": "ARGUS refused the content",
    "schema_unsupported": "the contract version is not supported",
    "payload_too_large": "the snapshot is too large",
    "idempotency_conflict": "the same id with other content",
    "lease_expired": "the lease expired",
    "lease_mismatch": "the lease does not match",
    "job_cancelled": "the job was cancelled in ARGUS",
    "budget_exceeded": "the budget was exceeded",
    "participation_not_confirmed": "participation is not confirmed",
    "sequence_gap": "a gap in seq, sent again",
}


@dataclass(frozen=True)
class Pending:
    """One outbox row as the batcher sees it."""

    event_id: str
    seq: int
    created_at: str
    evidence_ids: tuple[str, ...]
    type: str = ""
    retry_code: str = ""  # `evidence_missing`: refused once, waits for its snapshot


def pending_from_row(row: dict[str, object]) -> Pending:
    evidence = json.loads(str(row["evidence_ids_json"]))
    return Pending(
        str(row["event_id"]), int(str(row["seq"])), str(row["created_at"]), tuple(evidence),
        str(row.get("type") or ""), str(row.get("retry_code") or ""),
    )


def batch(rows: Sequence[Pending], uploads: dict[str, str],
          hold: tuple[str, ...] = ()) -> list[Pending]:
    """Leading pending events in seq order; they do not wait for the snapshot lane.

    Contract 3.1.0 (ARGUS 0.4.24.4, WINLOG 06.10.2026): an event before its snapshot is
    kept `evidence_pending` and applied when the snapshot arrives. Only an event ARGUS
    refused as `evidence_missing` waits for its snapshot uploaded again (`retry.py`), and
    an event of a type in `hold` waits (the run's end while its snapshots upload: its
    freshness checks name observations ARGUS applies only on the upload)."""
    out: list[Pending] = []
    for row in rows[:MAX_BATCH]:
        states = [uploads.get(e, "pending") for e in row.evidence_ids]
        if "rejected" in states:  # the snapshot never reaches ARGUS: `retry.lost`
            break
        if row.retry_code == "evidence_missing" and "pending" in states:
            break
        if row.type in hold:
            break
        out.append(row)
    return out


def age_s(created_at: str, now: datetime) -> float:
    return max(0.0, (now - datetime.fromisoformat(created_at)).total_seconds())


def ready(rows: Sequence[Pending], now: datetime, flush: bool) -> bool:
    """50 events, 2 s, or a whole page: its closing event is written (WINLOG 06.10.2026)."""
    if not rows:
        return False
    closed = rows[-1].type in CLOSING
    return flush or closed or len(rows) >= MAX_BATCH or age_s(rows[0].created_at, now) >= MAX_WAIT_S


def classify(status: int, code: str, retryable: bool) -> str:
    if status == 0:
        return ERROR_OFFLINE
    if status in (401, 403):
        return ERROR_AUTH
    if status == 409 and code in LEASE_CODES:
        return ERROR_LEASE
    if status == 409 and code == "idempotency_conflict":
        return ERROR_CONFLICT
    if status == 429:
        return ERROR_RATE
    if 400 <= status < 500 and not retryable:
        return ERROR_PERMANENT
    return ERROR_RETRY


def backoff_s(failures: int, retry_after: str | None = None) -> float:
    if retry_after and retry_after.strip().isdigit():
        return min(MAX_BACKOFF_S, float(retry_after.strip()))
    base = min(MAX_BACKOFF_S, 2.0 ** max(0, failures - 1))
    return base * random.uniform(0.5, 1.0)


def p95_s(pairs: Sequence[tuple[str, str]]) -> float | None:
    """95th percentile of (acked - created) seconds; None without data."""
    values = sorted(
        (datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds() for a, b in pairs
    )
    if not values:
        return None
    index = max(0, math.ceil(0.95 * len(values)) - 1)
    return round(values[index], 1)


def transport_state(error: str, pending: int, connected: bool, silent: bool = False) -> str:
    """`offline` only when not paired or when neither the heartbeat nor delivery got an
    answer (`Transport.silent`, owner 05.10.2026); a delivery request without an answer
    alone is a retry."""
    if not connected or silent:
        return STATE_OFFLINE
    if error in (ERROR_AUTH, ERROR_PERMANENT, ERROR_CONFLICT):
        return STATE_ERROR
    return STATE_SYNCING if pending else STATE_SYNCED


def status_code(status: int) -> str:
    """The code of a request ARGUS answered without an error body (a proxy page, 502)."""
    return f"http_{status}"


def reason(code: str) -> str:
    """Words for a rejection code, an `http_<status>` code or a class of request error."""
    if code.startswith("http_") and code[5:].isdigit():
        status = int(code[5:])
        return f"server error {status}" if status >= 500 else f"HTTP {status} without a reason"
    if code == ERROR_OFFLINE:
        return "no answer from ARGUS"
    if code == ERROR_AUTH:
        return "the token was rejected"
    rule = code.split("/", 1)[-1]  # `<code>/<rule>` of a 1.2 refusal: the rule says why
    return REASONS.get(rule, REASONS.get(code, code))


def elapsed_ms(started: float) -> int:
    """Milliseconds since `started` (`time.monotonic`)."""
    return int((time.monotonic() - started) * 1000)
