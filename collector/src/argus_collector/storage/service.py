"""Schema of the collector database (TZ_SELAIN section 10.2), one place."""

from __future__ import annotations

SCHEMA_VERSION = 2

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
    (
        2,
        """
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            batch_id TEXT NOT NULL,
            company_id TEXT NOT NULL,
            company_name TEXT NOT NULL,
            definition_json TEXT NOT NULL,
            claim_checkpoint_json TEXT,
            state TEXT NOT NULL,
            stage TEXT NOT NULL DEFAULT 'queued',
            run_id TEXT NOT NULL,
            lease_token TEXT NOT NULL,
            lease_generation INTEGER NOT NULL,
            lease_expires_at TEXT NOT NULL,
            drain_only INTEGER NOT NULL DEFAULT 0,
            started INTEGER NOT NULL DEFAULT 0,
            finished INTEGER NOT NULL DEFAULT 0,
            persons INTEGER NOT NULL DEFAULT 0,
            channels INTEGER NOT NULL DEFAULT 0,
            sources INTEGER NOT NULL DEFAULT 0,
            observations INTEGER NOT NULL DEFAULT 0,
            rejected INTEGER NOT NULL DEFAULT 0,
            last_reject_code TEXT NOT NULL DEFAULT '',
            result_status TEXT NOT NULL DEFAULT '',
            completion_reason TEXT NOT NULL DEFAULT '',
            detail TEXT NOT NULL DEFAULT '',
            claimed_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS checkpoints (
            run_id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL,
            state_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS entity_map (
            job_id TEXT NOT NULL,
            entity_key TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            first_run_id TEXT NOT NULL,
            PRIMARY KEY (job_id, entity_key)
        );
        CREATE TABLE IF NOT EXISTS commands (
            command_id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL,
            action TEXT NOT NULL,
            state_revision INTEGER NOT NULL,
            received_at TEXT NOT NULL,
            status TEXT NOT NULL,
            detail TEXT NOT NULL DEFAULT '',
            ack_delivered INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS outbox (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL UNIQUE,
            job_id TEXT NOT NULL,
            run_id TEXT NOT NULL,
            seq INTEGER NOT NULL,
            type TEXT NOT NULL,
            event_json TEXT NOT NULL,
            evidence_ids_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            code TEXT NOT NULL DEFAULT '',
            attempts INTEGER NOT NULL DEFAULT 0,
            sent_at TEXT,
            acked_at TEXT,
            canonical_contact_id TEXT,
            channel_status TEXT,
            UNIQUE (run_id, seq)
        );
        CREATE INDEX IF NOT EXISTS outbox_pending ON outbox (status, run_id, seq);
        CREATE TABLE IF NOT EXISTS evidence_uploads (
            evidence_id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL,
            run_id TEXT NOT NULL,
            local_evidence_id TEXT NOT NULL,
            metadata_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            code TEXT NOT NULL DEFAULT '',
            attempts INTEGER NOT NULL DEFAULT 0,
            acked_at TEXT
        );
        """,
    ),
]


def migrations() -> list[tuple[int, str]]:
    return list(MIGRATIONS)
