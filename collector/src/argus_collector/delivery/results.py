"""What ARGUS answered to one events request, written back to the outbox.

`evidence_missing` and `sequence_gap` stay pending (the snapshot is uploaded
again, the gap is filled by the next batch); other rejections are counted on
the company's row through the hooks and are not sent again.
"""

from __future__ import annotations

import json
import sqlite3

from argus_collector.api_client import contract as api
from argus_collector.delivery import repository as repo
from argus_collector.delivery import service
from argus_collector.delivery.hooks import DeliveryHooks
from argus_collector.runtime import contract as runtime

KEEP_PENDING = ("evidence_missing", "sequence_gap")


def apply(
    conn: sqlite3.Connection,
    hooks: DeliveryHooks,
    job_id: str,
    rows: dict[str, sqlite3.Row],
    resp: api.EventsResponse,
    elapsed_ms: int = 0,
) -> None:
    updates: list[tuple[str, str, str, str | None, str | None]] = []
    for result in resp.results:
        code, status = result.code or "", result.status.value
        row, item = rows[result.event_id], f"event {result.event_id} seq {result.seq}"
        if status == "rejected" and code in KEEP_PENDING:
            runtime.journal("delivery", f"job {job_id}: {row['type']} {item} rejected {code}"
                            f" ({service.reason(code)})")
            if code == "evidence_missing":
                repo.reset_upload(conn, json.loads(row["evidence_ids_json"]))
            continue
        if status == "rejected":
            hooks.rejected(conn, job_id, str(row["type"]), code, item)
        channel = result.channel_status.value if result.channel_status else None
        updates.append((result.event_id, status, code, result.canonical_contact_id, channel))
    repo.mark_events(conn, updates)
    accepted = sum(1 for u in updates if u[1] != "rejected")
    runtime.journal(
        "delivery",
        f"job {job_id}: {len(resp.results)} events sent, {accepted} accepted/duplicate,"
        f" {len(updates) - accepted} rejected, last_contiguous_seq={resp.last_contiguous_seq}"
        f" in {elapsed_ms} ms",
    )
    hooks.applied(conn, job_id, resp)
