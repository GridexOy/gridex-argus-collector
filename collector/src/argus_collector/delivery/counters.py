"""How much of the queue waits, failed or expired - counted through the indexes.

Until 0.4.8.11 every count scanned `outbox` and `evidence_uploads` whole, and the
Jono table asked once per job. After days of real runs the database is 100 MB, most
of it `event_json`, and a panel refresh took seconds: the window never finished
drawing. Migration 6 adds the indexes these queries read, and the queue asks for all
jobs in one go (`pending_by_job`).
"""

from __future__ import annotations

import sqlite3


def _counts(conn: sqlite3.Connection, table: str, where: str, args: tuple[str, ...]
            ) -> tuple[int, int, int]:
    sql = (
        f"SELECT COUNT(*) FILTER (WHERE status IN ('pending', 'waiting')),"
        f" COUNT(*) FILTER (WHERE status = 'rejected'), COUNT(*) FILTER (WHERE status = 'expired')"
        f" FROM {table} {where}"
    )
    row = conn.execute(sql, args).fetchone()
    return int(row[0] or 0), int(row[1] or 0), int(row[2] or 0)


def totals(conn: sqlite3.Connection, job_id: str | None = None) -> tuple[int, int, int]:
    """(pending, rejected, expired) events + uploads, for one job or all. An event given
    up whose seq carries a stand-in (`retry.py`) counts as rejected; `expired` is the
    queue of an earlier version, terminal since 0.4.8.11 and never sent again."""
    where, args = ("WHERE job_id = ?", (job_id,)) if job_id else ("", ())
    events = _counts(conn, "outbox", where, args)
    uploads = _counts(conn, "evidence_uploads", where, args)
    joiner = " AND" if where else " WHERE"
    lost = conn.execute(
        f"SELECT COUNT(*) FROM outbox {where}{joiner} replaced_type != ''", args
    ).fetchone()[0]
    return (events[0] + uploads[0], events[1] + uploads[1] + int(lost or 0),
            events[2] + uploads[2])


def pending_by_job(conn: sqlite3.Connection, job_ids: list[str]) -> dict[str, int]:
    """Waiting events + uploads of each job in one query: the Jono table asks for all of
    them at once instead of once per row (0.4.8.11)."""
    if not job_ids:
        return {}
    marks = ",".join("?" * len(job_ids))
    sql = (
        f"SELECT job_id, COUNT(*) FROM outbox WHERE job_id IN ({marks})"
        " AND status IN ('pending', 'waiting') GROUP BY job_id UNION ALL"
        f" SELECT job_id, COUNT(*) FROM evidence_uploads WHERE job_id IN ({marks})"
        " AND status = 'pending' GROUP BY job_id"
    )
    out: dict[str, int] = {}
    for job_id, count in conn.execute(sql, (*job_ids, *job_ids)):
        out[str(job_id)] = out.get(str(job_id), 0) + int(count)
    return out
