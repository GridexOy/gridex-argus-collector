"""Storage: schema creation, idempotent migration, path rules."""

from __future__ import annotations

from pathlib import Path

import pytest

from argus_collector.storage import contract, repository


def test_connect_creates_schema(tmp_path: Path) -> None:
    conn = contract.connect(tmp_path / "state" / "collector.db")
    tables = contract.table_names(conn)
    for name in ("model_calls", "evidence_manifest", "observations", "runs", "schema_version"):
        assert name in tables
    assert repository.current_version(conn) == contract.SCHEMA_VERSION
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    conn.close()


def test_migration_runs_once(tmp_path: Path) -> None:
    path = tmp_path / "collector.db"
    contract.connect(path).close()
    conn = contract.connect(path)
    rows = conn.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0]
    assert rows == contract.SCHEMA_VERSION, "one row per migration, none applied twice"
    conn.close()


def test_transaction_commits_once_and_rolls_back_on_error(tmp_path: Path) -> None:
    conn = contract.connect(tmp_path / "c.db")
    with contract.transaction(conn):
        conn.execute("INSERT INTO commands (command_id, job_id, action, state_revision,"
                     " received_at, status) VALUES ('c1', 'j', 'pause', 1, 't', 'applied')")
        with contract.transaction(conn):  # nested: joins, does not commit early
            assert conn.in_transaction
    with pytest.raises(RuntimeError), contract.transaction(conn):
        conn.execute("INSERT INTO commands (command_id, job_id, action, state_revision,"
                     " received_at, status) VALUES ('c2', 'j', 'pause', 1, 't', 'applied')")
        raise RuntimeError("boom")
    ids = [r[0] for r in conn.execute("SELECT command_id FROM commands")]
    assert ids == ["c1"]
    for name in ("jobs", "outbox", "evidence_uploads", "entity_map", "checkpoints"):
        assert name in contract.table_names(conn)


def test_db_path_is_under_user_data_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ARGUS_COLLECTOR_HOME", str(tmp_path))
    assert contract.db_path() == tmp_path / "state" / "collector.db"
