"""Single entry point of the `storage` module: the collector SQLite database.

One file, `<user_data_dir>/state/collector.db` (TZ_SELAIN section 10.2), WAL
mode, schema created by `connect()`. Other modules write only their own
tables through their `repository.py`; the table definitions live here so
there is one migration history.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from argus_collector.runtime import contract as runtime
from argus_collector.storage import repository, service

__all__ = ["SCHEMA_VERSION", "connect", "db_path", "table_names"]

SCHEMA_VERSION = service.SCHEMA_VERSION
STATE_DIRNAME = "state"
DB_FILENAME = "collector.db"


def db_path() -> Path:
    return runtime.user_data_dir() / STATE_DIRNAME / DB_FILENAME


def connect(path: Path | None = None) -> sqlite3.Connection:
    """Open (and create) the database with the current schema; WAL, autocommit off."""
    target = path or db_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = repository.open_connection(target)
    repository.migrate(conn, service.migrations())
    return conn


def table_names(conn: sqlite3.Connection) -> list[str]:
    return repository.table_names(conn)
