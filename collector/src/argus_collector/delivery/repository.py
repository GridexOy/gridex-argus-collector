"""SQLite of the delivery module: the `outbox` and `evidence_uploads` tables.

Writes that belong to a caller's transaction (`insert_event`, `insert_upload`)
never commit; the delivery thread's own updates commit at once.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime

DONE = ("accepted", "duplicate", "rejected")
ACKED = (*DONE, "waiting")  # seq taken by ARGUS (a waiting event awaits its verdict only)


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def next_seq(conn: sqlite3.Connection, run_id: str) -> int:
    row = conn.execute("SELECT COALESCE(MAX(seq), 0) FROM outbox WHERE run_id = ?", (run_id,))
    return int(row.fetchone()[0]) + 1


def insert_event(
    conn: sqlite3.Connection,
    ids: tuple[str, str, str, int],
    event_type: str,
    event_json: dict[str, object],
    evidence_ids: list[str],
) -> None:
    event_id, job_id, run_id, seq = ids
    conn.execute(
        "INSERT INTO outbox (event_id, job_id, run_id, seq, type, event_json, evidence_ids_json,"
        " created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (event_id, job_id, run_id, seq, event_type, json.dumps(event_json, ensure_ascii=False),
         json.dumps(evidence_ids), now_iso()),
    )


def insert_upload(
    conn: sqlite3.Connection, ids: tuple[str, str, str, str], metadata: dict[str, object]
) -> bool:
    evidence_id, job_id, run_id, local_id = ids
    cursor = conn.execute(
        "INSERT OR IGNORE INTO evidence_uploads (evidence_id, job_id, run_id, local_evidence_id,"
        " metadata_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (evidence_id, job_id, run_id, local_id, json.dumps(metadata, ensure_ascii=False),
         now_iso()),
    )
    return cursor.rowcount == 1


def pending_uploads(conn: sqlite3.Connection, limit: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM evidence_uploads WHERE status = 'pending' ORDER BY created_at LIMIT ?",
        (limit,),
    ).fetchall()


def mark_upload(conn: sqlite3.Connection, evidence_id: str, status: str, code: str) -> None:
    with conn:
        conn.execute(
            "UPDATE evidence_uploads SET status = ?, code = ?, attempts = attempts + 1,"
            " acked_at = ? WHERE evidence_id = ?",
            (status, code, now_iso(), evidence_id),
        )


def upload_states(conn: sqlite3.Connection, evidence_ids: list[str]) -> dict[str, str]:
    if not evidence_ids:
        return {}
    marks = ",".join("?" * len(evidence_ids))
    rows = conn.execute(
        f"SELECT evidence_id, status FROM evidence_uploads WHERE evidence_id IN ({marks})",
        evidence_ids,
    )
    return {str(r[0]): str(r[1]) for r in rows}


def pending_runs(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    """Runs with events to send or a verdict to ask (`waiting`: evidence_pending)."""
    rows = conn.execute(
        "SELECT job_id, run_id, MIN(id) FROM outbox WHERE status IN ('pending', 'waiting')"
        " GROUP BY job_id, run_id ORDER BY MIN(id)"
    )
    return [(str(r[0]), str(r[1])) for r in rows]


def waiting_events(conn: sqlite3.Connection, run_id: str, limit: int = 50) -> list[sqlite3.Row]:
    """Events ARGUS keeps evidence_pending, once no snapshot of the run is left to upload."""
    if pending_upload_ids(conn, run_id):
        return []
    return conn.execute(
        "SELECT * FROM outbox WHERE run_id = ? AND status = 'waiting' ORDER BY seq LIMIT ?",
        (run_id, limit),
    ).fetchall()


def pending_events(conn: sqlite3.Connection, run_id: str, limit: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM outbox WHERE run_id = ? AND status = 'pending' ORDER BY seq LIMIT ?",
        (run_id, limit),
    ).fetchall()


def mark_events(
    conn: sqlite3.Connection, updates: list[tuple[str, str, str, str | None, str | None]]
) -> None:
    """(event_id, status, code, canonical_contact_id, channel_status) per row."""
    stamp = now_iso()
    with conn:
        for event_id, status, code, canonical, channel in updates:
            acked = stamp if status in ACKED else None
            conn.execute(
                "UPDATE outbox SET status = ?, code = ?, attempts = attempts + 1, sent_at = ?,"
                " acked_at = ?, canonical_contact_id = COALESCE(?, canonical_contact_id),"
                " channel_status = COALESCE(?, channel_status) WHERE event_id = ?",
                (status, code, stamp, acked, canonical, channel, event_id),
            )


def reset_upload(conn: sqlite3.Connection, evidence_ids: list[str]) -> None:
    with conn:
        for evidence_id in evidence_ids:
            conn.execute(
                "UPDATE evidence_uploads SET status = 'pending' WHERE evidence_id = ?",
                (evidence_id,),
            )


def totals(conn: sqlite3.Connection, job_id: str | None = None) -> tuple[int, int]:
    """(pending events + uploads, rejected events + uploads), for one job or all; an event
    given up whose seq carries a stand-in (`retry.py`) counts as rejected."""
    where, args = ("WHERE job_id = ?", (job_id,)) if job_id else ("", ())
    sql = (
        "SELECT SUM(status IN ('pending', 'waiting')), SUM(status = 'rejected' OR lost != '')"
        " FROM ("
        f"SELECT status, replaced_type AS lost FROM outbox {where} UNION ALL"
        f" SELECT status, '' FROM evidence_uploads {where})"
    )
    row = conn.execute(sql, args * 2).fetchone()
    return int(row[0] or 0), int(row[1] or 0)


def acked_since(conn: sqlite3.Connection, since: str) -> list[tuple[str, str]]:
    """(created, acked) of events queued and acknowledged since `since`: an event that
    waited in the queue from before is not a send of this window (owner 06.10.2026)."""
    rows = conn.execute(
        "SELECT created_at, acked_at FROM outbox WHERE acked_at IS NOT NULL AND acked_at >= ?"
        " AND created_at >= ?",
        (since, since),
    )
    return [(str(r[0]), str(r[1])) for r in rows]


def run_rows(conn: sqlite3.Connection, run_id: str) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM outbox WHERE run_id = ? ORDER BY seq", (run_id,)).fetchall()


def pending_upload_ids(conn: sqlite3.Connection, run_id: str) -> list[str]:
    rows = conn.execute(
        "SELECT evidence_id FROM evidence_uploads WHERE run_id = ? AND status = 'pending'",
        (run_id,),
    )
    return [str(r[0]) for r in rows]


def job_run_ids(conn: sqlite3.Connection, job_id: str) -> list[str]:
    rows = conn.execute(
        "SELECT run_id, MIN(id) FROM outbox WHERE job_id = ? GROUP BY run_id ORDER BY MIN(id)",
        (job_id,),
    )
    return [str(r[0]) for r in rows]


def local_evidence_id(conn: sqlite3.Connection, evidence_id: str) -> str | None:
    row = conn.execute(
        "SELECT local_evidence_id FROM evidence_uploads WHERE evidence_id = ?", (evidence_id,)
    ).fetchone()
    return str(row[0]) if row else None


def rejected_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Rejected events (given-up ones by their own id) and snapshots, the latest first."""
    return conn.execute(
        "SELECT job_id, type AS kind, event_id AS item_id, seq, code, sent_at AS at"
        " FROM outbox WHERE status = 'rejected' AND replaced_type = '' UNION ALL"
        " SELECT job_id, replaced_type, replaced_event_id, seq, retry_code, sent_at"
        " FROM outbox WHERE replaced_type != '' UNION ALL"
        " SELECT job_id, 'evidence', evidence_id, NULL, code, acked_at"
        " FROM evidence_uploads WHERE status = 'rejected' ORDER BY at DESC"
    ).fetchall()
