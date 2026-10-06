"""An event ARGUS rejected but that may still pass (owner 05.10.2026, 0.4.8.5).

`evidence_missing`: the snapshots the event names are queued again and the
event waits for them (`service.batch`), then goes again. When a snapshot is not
stored here any more, or the same code came back after 3 retries, the event is
given up: `Hylätty: todiste puuttuu` on the company's row, counted in
Lähetysvirhe, never sent again. ARGUS does not take the seq of an event it
rejected this way (the contract: the seq stays free, later events are
`sequence_gap`), so the seq then carries a stand-in `source.blocked` event
without evidence that says what was lost; the rest of the run goes on.
`sequence_gap` follows from an earlier event and is not counted.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime

from argus_collector.api_client import contract as api
from argus_collector.delivery import repository as repo
from argus_collector.delivery import service
from argus_collector.delivery.hooks import DeliveryHooks
from argus_collector.evidence import contract as evidence
from argus_collector.runtime import contract as runtime

MAX_RETRIES = 3
COUNTED = ("evidence_missing",)


def after_rejection(conn: sqlite3.Connection, hooks: DeliveryHooks, job_id: str,
                    row: sqlite3.Row, code: str, last_seq: int) -> None:
    """A kept-pending rejection of `row`: retry it (snapshots first) or give it up."""
    head = f"job {job_id}: {row['type']} event {row['event_id']} seq {row['seq']} rejected {code}"
    if code not in COUNTED:
        return
    ids = [str(e) for e in json.loads(row["evidence_ids_json"])]
    count = int(row["retry_count"]) + 1 if row["retry_code"] == code else 1
    lost = next((e for e in ids if not _stored(conn, e)), None)
    if lost is not None:
        give_up(conn, hooks, job_id, row, code, last_seq, f"snapshot {lost} is not stored here")
    elif count > MAX_RETRIES:
        give_up(conn, hooks, job_id, row, code, last_seq, f"{code} after {MAX_RETRIES} retries")
    else:
        before = repo.upload_states(conn, ids)
        _note_retry(conn, str(row["event_id"]), code, count)
        repo.reset_upload(conn, ids)
        runtime.journal("delivery", f"{head} ({service.reason(code)}): snapshot uploaded again"
                        f" first (was {before}), retry {count} of {MAX_RETRIES}")


def lost(conn: sqlite3.Connection, hooks: DeliveryHooks, job_id: str, row: sqlite3.Row,
         uploads: dict[str, str]) -> bool:
    """An event whose snapshot upload was refused is given up before it is sent: ARGUS
    would keep it `evidence_pending` for 24 h and then refuse it (contract 3.1.0)."""
    ids = [str(e) for e in json.loads(row["evidence_ids_json"])]
    gone = next((e for e in ids if uploads.get(e) == "rejected"), None)
    if gone is None:
        return False
    why = "is not stored here" if not _stored(conn, gone) else "was refused"
    give_up(conn, hooks, job_id, row, "evidence_missing", 0, f"snapshot {gone} {why}")
    return True


def give_up(conn: sqlite3.Connection, hooks: DeliveryHooks, job_id: str, row: sqlite3.Row,
            code: str, last_seq: int, why: str) -> None:
    """Never sent again; a stand-in takes its seq unless ARGUS already counted the seq."""
    item = f"event {row['event_id']} seq {row['seq']} ({why})"
    hooks.rejected(conn, job_id, str(row["type"]), code, item)
    if last_seq >= int(row["seq"]):
        repo.mark_events(conn, [(str(row["event_id"]), "rejected", code, None, None)])
        return
    stand_in = _stand_in(conn, row, code, why)
    with conn:
        conn.execute(
            "UPDATE outbox SET event_id = ?, type = ?, event_json = ?, evidence_ids_json = '[]',"
            " status = 'pending', code = '', replaced_type = type, replaced_event_id = event_id,"
            " retry_code = ? WHERE event_id = ?",
            (stand_in.event_id, stand_in.type, json.dumps(api.to_json(stand_in)), code,
             row["event_id"]),
        )
    runtime.journal("delivery", f"job {job_id}: seq {row['seq']} carries source.blocked"
                    f" {stand_in.event_id} instead of {row['type']} {row['event_id']}")


def _stored(conn: sqlite3.Connection, evidence_id: str) -> bool:
    local = repo.local_evidence_id(conn, evidence_id)
    return local is not None and evidence.load_snapshot(conn, local) is not None


def _note_retry(conn: sqlite3.Connection, event_id: str, code: str, count: int) -> None:
    with conn:
        conn.execute("UPDATE outbox SET retry_code = ?, retry_count = ?, attempts = attempts + 1"
                     " WHERE event_id = ?", (code, count, event_id))


def _stand_in(conn: sqlite3.Connection, row: sqlite3.Row, code: str,
              why: str) -> api.SourceBlockedEvent:
    ids = [str(e) for e in json.loads(row["evidence_ids_json"])]
    url = next((u for u in (_page_url(conn, e) for e in ids) if u), "about:blank")
    payload = api.SourcePayload(
        source_id=f"lost:{row['event_id']}", url=url, state_key="", parent_source_id=None,
        status=code, evidence_ids=[], detail=f"{row['type']} {row['event_id']} not delivered:"
        f" {why}",
    )
    return api.SourceBlockedEvent(
        event_id=str(uuid.uuid4()), job_id=str(row["job_id"]), run_id=str(row["run_id"]),
        seq=int(row["seq"]), occurred_at=datetime.now(UTC).isoformat(timespec="milliseconds"),
        payload=payload,
    )


def _page_url(conn: sqlite3.Connection, evidence_id: str) -> str:
    found = conn.execute("SELECT metadata_json FROM evidence_uploads WHERE evidence_id = ?",
                         (evidence_id,)).fetchone()
    return str(json.loads(found[0]).get("final_url") or "") if found else ""
