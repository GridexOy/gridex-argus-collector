"""Single entry point of the `evidence` module: snapshots, hashes, locators.

A fact is only a fact with a snapshot, a locator and a quote (RULES E1-E3).
Snapshots live under `<user_data_dir>/evidence/<sha256[:2]>/<sha256>.html`
plus the canonical text next to it as `.txt`; the manifest row is in the
`evidence_manifest` table of the collector database.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from argus_collector.evidence import repository, service
from argus_collector.evidence.service import Snapshot, TextSpan
from argus_collector.runtime import contract as runtime

__all__ = [
    "Snapshot",
    "TextSpan",
    "canonical_text",
    "evidence_dir",
    "find_span",
    "sha256_text",
    "store_snapshot",
]

EVIDENCE_DIRNAME = "evidence"


def evidence_dir() -> Path:
    return runtime.user_data_dir() / EVIDENCE_DIRNAME


def canonical_text(text: str) -> str:
    """NFC, CRLF -> LF, whitespace runs inside a line collapsed, blank lines dropped."""
    return service.canonical_text(text)


def sha256_text(text: str) -> str:
    return service.sha256_text(text)


def find_span(text: str, quote: str) -> TextSpan | None:
    """Locate `quote` in canonical `text`: exact first, then whitespace-insensitive.

    Returns the span in code points `[start, end)` with the quote as it
    appears in the text, or None when the quote is not there.
    """
    return service.find_span(text, quote)


def store_snapshot(
    conn: sqlite3.Connection,
    url: str,
    final_url: str,
    html: str,
    text: str,
    base_dir: Path | None = None,
) -> Snapshot:
    """Write html + canonical text under the evidence dir and record the manifest row.

    `evidence_id` is the sha256 of the html; storing the same html twice
    returns the same snapshot. Files are written atomically (tmp + rename).
    """
    canonical = service.canonical_text(text)
    snapshot = service.describe_snapshot(
        url, final_url, html, canonical, base_dir or evidence_dir()
    )
    repository.write_files(snapshot, html, canonical)
    repository.insert_manifest(conn, snapshot)
    return snapshot
