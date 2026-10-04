# storage

The collector database: one SQLite file
`%LOCALAPPDATA%\Gridex\ArgusCollector\state\collector.db` (TZ_SELAIN
section 10.2), WAL mode, schema applied by `connect()`.

Entry point: `contract.py`.

| Function | What it does |
|---|---|
| `db_path()` | `<user_data_dir>/state/collector.db` |
| `connect(path=None)` | opens (creates) the file, applies pending migrations, returns the connection (`check_same_thread=False`: the walk thread and the panel thread share it; writes are short transactions) |
| `table_names(conn)` | tables present, for tests and diagnostics |
| `transaction(conn)` | 0.4.3.0: `BEGIN IMMEDIATE` ... `COMMIT` (rollback on error); a nested call joins it. An observation and its outbox events are written in one of these |

`service.py` holds the ordered migrations (`schema_version`, `model_calls`,
`evidence_manifest`, `runs`, `observations`); an applied entry is never
edited, a change is a new version. Other modules write only their own
tables from their `repository.py`: `models` -> `model_calls`, `evidence`
-> `evidence_manifest`, `walk` -> `runs`, `observations`; migration 2
(0.4.3.0): `scheduler` -> `jobs`, `checkpoints`, `entity_map`, `commands`;
`delivery` -> `outbox`, `evidence_uploads`.
