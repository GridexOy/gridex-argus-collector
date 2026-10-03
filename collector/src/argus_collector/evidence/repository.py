"""Disk and SQLite access of the evidence module: snapshot files, manifest rows."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from argus_collector.evidence.service import Snapshot


def _write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def write_files(snapshot: Snapshot, html: str, text: str) -> None:
    """Write html and canonical text; an existing identical snapshot is left alone."""
    if not snapshot.html_path.is_file():
        _write_atomic(snapshot.html_path, html)
    if not snapshot.text_path.is_file():
        _write_atomic(snapshot.text_path, text)


def insert_manifest(conn: sqlite3.Connection, snapshot: Snapshot) -> None:
    with conn:
        conn.execute(
            "INSERT OR IGNORE INTO evidence_manifest (evidence_id, url, final_url, fetched_at,"
            " html_sha256, text_sha256, html_path, text_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                snapshot.evidence_id,
                snapshot.url,
                snapshot.final_url,
                snapshot.fetched_at,
                snapshot.html_sha256,
                snapshot.text_sha256,
                str(snapshot.html_path),
                str(snapshot.text_path),
            ),
        )


def manifest_row(conn: sqlite3.Connection, evidence_id: str) -> dict[str, str] | None:
    row = conn.execute(
        "SELECT * FROM evidence_manifest WHERE evidence_id = ?", (evidence_id,)
    ).fetchone()
    return None if row is None else {k: str(row[k]) for k in row.keys()}
