"""SQLite of the scheduler: `jobs`, `checkpoints`, `entity_map`, `commands`.

Functions named `*_tx` run inside the caller's transaction (no commit);
the others commit at once.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from typing import Any

JOB_COLUMNS = (
    "job_id, batch_id, company_id, company_name, definition_json, state, stage, run_id,"
    " lease_token, lease_generation, lease_expires_at, drain_only, started, finished,"
    " persons, channels, sources, observations, rejected, last_reject_code, result_status,"
    " completion_reason, detail, claimed_at, updated_at"
)


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def job(conn: sqlite3.Connection, job_id: str) -> sqlite3.Row | None:
    row: sqlite3.Row | None = conn.execute(
        f"SELECT {JOB_COLUMNS} FROM jobs WHERE job_id = ?", (job_id,)
    ).fetchone()
    return row


def jobs(conn: sqlite3.Connection, states: tuple[str, ...] | None = None) -> list[sqlite3.Row]:
    if states is None:
        sql = f"SELECT {JOB_COLUMNS} FROM jobs ORDER BY claimed_at, job_id"
        return conn.execute(sql).fetchall()
    marks = ",".join("?" * len(states))
    sql = f"SELECT {JOB_COLUMNS} FROM jobs WHERE state IN ({marks}) ORDER BY claimed_at, job_id"
    return conn.execute(sql, states).fetchall()


def recent_jobs(conn: sqlite3.Connection, since: str, active: tuple[str, ...]) -> list[sqlite3.Row]:
    marks = ",".join("?" * len(active))
    sql = (
        f"SELECT {JOB_COLUMNS} FROM jobs WHERE state IN ({marks}) OR updated_at >= ?"
        " ORDER BY claimed_at, job_id"
    )
    return conn.execute(sql, (*active, since)).fetchall()


def insert_job_tx(conn: sqlite3.Connection, values: dict[str, Any]) -> None:
    stamp = now_iso()
    conn.execute(
        "INSERT INTO jobs (job_id, batch_id, company_id, company_name, definition_json, state,"
        " stage, run_id, lease_token, lease_generation, lease_expires_at, claimed_at, updated_at)"
        " VALUES (:job_id, :batch_id, :company_id, :company_name, :definition_json, :state,"
        " :stage, :run_id, :lease_token, :lease_generation, :lease_expires_at, :stamp, :stamp)",
        {**values, "stamp": stamp},
    )


def update_job_tx(conn: sqlite3.Connection, job_id: str, **fields: Any) -> None:
    if not fields:
        return
    sets = ", ".join(f"{name} = :{name}" for name in fields)
    conn.execute(
        f"UPDATE jobs SET {sets}, updated_at = :stamp WHERE job_id = :job_id",
        {**fields, "job_id": job_id, "stamp": now_iso()},
    )


def update_job(conn: sqlite3.Connection, job_id: str, **fields: Any) -> None:
    with conn:
        update_job_tx(conn, job_id, **fields)


def bump_job_tx(conn: sqlite3.Connection, job_id: str, **deltas: int) -> None:
    sets = ", ".join(f"{name} = {name} + :{name}" for name in deltas)
    conn.execute(
        f"UPDATE jobs SET {sets}, updated_at = :stamp WHERE job_id = :job_id",
        {**deltas, "job_id": job_id, "stamp": now_iso()},
    )


def map_entity_tx(
    conn: sqlite3.Connection, job_id: str, key: str, entity: tuple[str, str], run_id: str
) -> bool:
    """True when the entity is new for the job (the counters then grow)."""
    entity_id, entity_type = entity
    cursor = conn.execute(
        "INSERT OR IGNORE INTO entity_map (job_id, entity_key, entity_id, entity_type,"
        " first_run_id) VALUES (?, ?, ?, ?, ?)",
        (job_id, key, entity_id, entity_type, run_id),
    )
    return cursor.rowcount == 1


def entity_types(conn: sqlite3.Connection, job_id: str) -> dict[str, str]:
    rows = conn.execute("SELECT entity_key, entity_type FROM entity_map WHERE job_id = ?",
                        (job_id,))
    return {str(r[0]): str(r[1]) for r in rows}


def entity_counts(conn: sqlite3.Connection, job_id: str) -> dict[str, int]:
    rows = conn.execute(
        "SELECT entity_type, COUNT(*) FROM entity_map WHERE job_id = ? GROUP BY entity_type",
        (job_id,),
    )
    return {str(r[0]): int(r[1]) for r in rows}


def save_checkpoint_tx(
    conn: sqlite3.Connection, run_id: str, job_id: str, state: dict[str, Any]
) -> None:
    conn.execute(
        "INSERT INTO checkpoints (run_id, job_id, state_json, updated_at) VALUES (?, ?, ?, ?)"
        " ON CONFLICT(run_id) DO UPDATE SET state_json = excluded.state_json,"
        " updated_at = excluded.updated_at",
        (run_id, job_id, json.dumps(state, ensure_ascii=False), now_iso()),
    )


def checkpoint(conn: sqlite3.Connection, run_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT state_json FROM checkpoints WHERE run_id = ?", (run_id,)).fetchone()
    return None if row is None else dict(json.loads(row[0]))


def latest_checkpoint(conn: sqlite3.Connection, job_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT state_json FROM checkpoints WHERE job_id = ? ORDER BY updated_at DESC LIMIT 1",
        (job_id,),
    ).fetchone()
    return None if row is None else dict(json.loads(row[0]))


def command(conn: sqlite3.Connection, command_id: str) -> sqlite3.Row | None:
    row: sqlite3.Row | None = conn.execute(
        "SELECT * FROM commands WHERE command_id = ?", (command_id,)
    ).fetchone()
    return row


def insert_command(conn: sqlite3.Connection, values: tuple[str, str, str, int, str, str]) -> None:
    with conn:
        conn.execute(
            "INSERT OR IGNORE INTO commands (command_id, job_id, action, state_revision,"
            " received_at, status, detail) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (*values[:4], now_iso(), *values[4:]),
        )


def unsent_acks(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM commands WHERE ack_delivered = 0 ORDER BY received_at"
    ).fetchall()


def mark_acks_sent(conn: sqlite3.Connection, command_ids: list[str]) -> None:
    with conn:
        for command_id in command_ids:
            conn.execute(
                "UPDATE commands SET ack_delivered = 1 WHERE command_id = ?", (command_id,)
            )


def resend_ack(conn: sqlite3.Connection, command_id: str) -> None:
    with conn:
        conn.execute(
            "UPDATE commands SET ack_delivered = 0, status = 'already_applied'"
            " WHERE command_id = ?",
            (command_id,),
        )
