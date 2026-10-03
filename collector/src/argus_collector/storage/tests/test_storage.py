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
    assert rows == 1
    conn.close()


def test_db_path_is_under_user_data_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ARGUS_COLLECTOR_HOME", str(tmp_path))
    assert contract.db_path() == tmp_path / "state" / "collector.db"
