# contract_server

Reference **test stand** for the whole of `docs/ARGUS20_COLLECTOR_OPENAPI.json`
(wire schema 1.1, base path `/api/collector`). Stdlib only (`http.server`),
never deployed: it stands in for the production `/api/collector` until block 6,
so the collector can be built and tested against real HTTP.

```
python -m contract_server.server --port 8900 [--token TOKEN:WORKER_ID]...
    [--system-token T]... [--state PATH] [--lease-seconds 180]
python -m contract_server.stand batch --companies FILE.json [--only c1,c2]
    [--rerun-reason TEXT] [--client-request-id X] [--base-url URL] [--system-token T]
python -m contract_server.stand control JOB_ID pause|resume|cancel|continue
python -m contract_server.stand job|batch-status|worker|contacts ID
```

`server.start(host, port, tokens=..., system_tokens=..., state_path=..., now=...,
lease_seconds=...)` runs the same server in a daemon thread (tests, panel).

## Tokens
Worker tokens `{token: worker_id}`, default `test-token-abc` -> `worker-main-pc`;
system tokens default `{"system-token-xyz"}`. A worker token on a System
endpoint (or the reverse), a missing or unknown token -> 401 `unauthorized`;
`server.registry.revoke(worker_id)` -> 403 `worker_revoked`. Tokens and
revocations live in memory only.

## Behaviour
- One door: every request body is validated against its OpenAPI schema by
  `schema.py` (400 `invalid_input`); the tests validate every response too.
- Batches (R8, rerun_reason, idempotency), claim with M1 pinning and lazy lease
  expiry, heartbeat renewal + commands/acks, evidence (multipart, hashes, size
  limits, idempotency), events (ordered seq, duplicates, sequence_gap,
  evidence_missing, quote checks, K7 hosts, field_audit, K3 channel status),
  job.finished with auto-continue, reconcile resume/drain_only, control with
  optimistic `state_revision`, job/batch/worker status.
- A finished run's lease token keeps drain rights (replays stay duplicates).
- `--state PATH` saves the whole state as JSON after every POST (atomic) and
  loads it at start; evidence bytes and texts go to `PATH.evidence/`.

## Stand-only endpoints (not in the contract, SystemBearer)
`GET /_stand/jobs/{job_id}/contacts` (contacts with observations and channel
status, recorded rejections, model calls, sources) and
`GET /_stand/evidence/{evidence_id}` (metadata + text used for quote checks).

## Layout
`server.py` (start/CLI), `httpio.py`, `routes.py` (auth, dispatch), `context.py`,
`state.py`, `persistence.py`, `schema.py` + `openapi.py`, one module per
endpoint (`batches`, `claim`, `heartbeat`, `evidence`, `events` with
`event_apply`/`contacts`/`channels`/`finish`, `reconcile`, `control`,
`status`, `stand_views`), `stand.py` (owner CLI), `tests/`.
