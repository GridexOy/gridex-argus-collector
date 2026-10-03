"""Schema of the collector database (TZ_SELAIN section 10.2), one place."""

from __future__ import annotations

SCHEMA_VERSION = 1

# Ordered list of (version, sql) applied once each; never edit an applied entry.
MIGRATIONS: list[tuple[int, str]] = [
    (
        1,
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS model_calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            called_at TEXT NOT NULL,
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            purpose TEXT NOT NULL,
            prompt_tokens INTEGER NOT NULL DEFAULT 0,
            completion_tokens INTEGER NOT NULL DEFAULT 0,
            elapsed_ms INTEGER NOT NULL DEFAULT 0,
            cost_eur REAL NOT NULL DEFAULT 0,
            ok INTEGER NOT NULL DEFAULT 1,
            error TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS evidence_manifest (
            evidence_id TEXT PRIMARY KEY,
            url TEXT NOT NULL,
            final_url TEXT NOT NULL,
            fetched_at TEXT NOT NULL,
            html_sha256 TEXT NOT NULL,
            text_sha256 TEXT NOT NULL,
            html_path TEXT NOT NULL,
            text_path TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            start_url TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            pages INTEGER NOT NULL DEFAULT 0,
            contacts INTEGER NOT NULL DEFAULT 0,
            result TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            evidence_id TEXT NOT NULL,
            url TEXT NOT NULL,
            observed_at TEXT NOT NULL,
            name TEXT NOT NULL,
            title TEXT,
            phone TEXT,
            email TEXT,
            fields_json TEXT NOT NULL
        );
        """,
    ),
]


def migrations() -> list[tuple[int, str]]:
    return list(MIGRATIONS)
