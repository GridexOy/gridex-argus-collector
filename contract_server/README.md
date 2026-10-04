# contract_server

Local reference implementation of one slice of
`docs/ARGUS20_COLLECTOR_OPENAPI.json`: `POST /api/collector/workers/heartbeat`.
Stdlib only, no web framework -- same spirit as `test_site/server.py`.

This is a **test double**, not the real ARGUS server. It stands in for the
production `/api/collector` (built separately, pair B1 onward) so the
collector's `api_client` can be developed and tested against a real HTTP
endpoint before that server exists. It never runs against prod.

```
python -m contract_server.server --port 8900
python -m contract_server.server --port 8900 --token my-token:worker-x
```

`server.start(host, port, tokens=...)` starts the same server in a daemon
thread for tests and for the panel's "Testaa yhteys" button.

## Seeding a test token

One worker token is pre-registered by default: `test-token-abc` ->
`worker-main-pc` (`registry.DEFAULT_TOKENS`). Pass your own
`tokens={"token": "worker_id"}` to `server.start()` / `server.make_server()`,
or `--token TOKEN:WORKER_ID` (repeatable) on the CLI, to add others. Tokens
live in memory only: nothing persists across restarts, and there is no
hashing (the real server's token hashing and revocation are pair B1's work,
out of scope here).

## Scope

Only the heartbeat endpoint exists. It validates `schema_versions` contains
`"1.1"` (400 `schema_unsupported` otherwise), rejects an unknown or missing
bearer token with 401 `unauthorized`, rejects a malformed JSON body with 400
`invalid_input`, and otherwise replies 200 with an empty `leases`/`commands`
list -- no jobs exist yet in A1; claim and job flows are later pairs.
`/batches`, `/jobs/*` and `/workers/{id}/status` are not implemented.
