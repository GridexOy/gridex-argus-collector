"""SQLite rows of the walk module: `runs` and `observations`."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import UTC, datetime

from argus_collector.extraction.contract import Contact
from argus_collector.walk.service import contact_json


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def start_run(conn: sqlite3.Connection, start_url: str) -> str:
    run_id = uuid.uuid4().hex
    with conn:
        conn.execute(
            "INSERT INTO runs (run_id, start_url, started_at) VALUES (?, ?, ?)",
            (run_id, start_url, _now()),
        )
    return run_id


def finish_run(
    conn: sqlite3.Connection, run_id: str, pages: int, contacts: int, result: str
) -> None:
    with conn:
        conn.execute(
            "UPDATE runs SET finished_at = ?, pages = ?, contacts = ?, result = ? WHERE run_id = ?",
            (_now(), pages, contacts, result, run_id),
        )


def insert_observation(
    conn: sqlite3.Connection, run_id: str, evidence_id: str, url: str, contact: Contact
) -> int:
    with conn:
        cursor = conn.execute(
            "INSERT INTO observations (run_id, evidence_id, url, observed_at, name, title,"
            " phone, email, fields_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                evidence_id,
                url,
                _now(),
                contact.name.value,
                contact.title.value if contact.title else None,
                contact.phone.value if contact.phone else None,
                contact.email.value if contact.email else None,
                contact_json(contact),
            ),
        )
    return int(cursor.lastrowid or 0)


def observations_of_run(conn: sqlite3.Connection, run_id: str) -> list[dict[str, object]]:
    rows = conn.execute(
        "SELECT * FROM observations WHERE run_id = ? ORDER BY id", (run_id,)
    ).fetchall()
    return [{k: row[k] for k in row.keys()} for row in rows]
