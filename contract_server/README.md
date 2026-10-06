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
python -m contract_server.stand company-contacts COMPANY_ID
```

`server.start(host, port, tokens=..., system_tokens=..., state_path=..., now=...,
lease_seconds=...)` runs the same server in a daemon thread (tests, panel).

## Tokens
Worker tokens `{token: worker_id}`, default `test-token-abc` -> `worker-main-pc`;
system tokens default `{"system-token-xyz"}`. A worker token on a System
endpoint (or the reverse), a missing or unknown token -> 401 `unauthorized`;
`server.registry.revoke(worker_id)` -> 403 `worker_revoked`. Tokens and
revocations live in memory only. At start the server prints one pairing key
per worker token, e.g. `pairing key worker-main-pc:
argus://pair?url=http%3A%2F%2F127.0.0.1%3A8900&worker=worker-main-pc&token=test-token-abc`
(`server.pairing_key(address, worker_id, token)`): the owner pastes it into
the panel's Yhteys block ("Paritusavain" -> "Yhdistä").

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
- needs_attention: heartbeats keep renewing the run's lease; an accepted
  `job.progress`, `source.*` or `contact.*` of the current run returns the job
  to `running`; control `resume` is allowed (-> running with a live lease,
  else queued) and goes to the worker as a Command, as for paused.

## History and coverage (pair 4; the stand's own rules beyond the contract)
- **Canonical contact per company** (`identity.py`): a person by (company_id,
  full name casefolded, whitespace collapsed) from its `full_name`
  observation; office / organization_channel / department / unassigned_channel
  by (company_id, entity_type, first channel value: email casefolded, phone
  `+` and digits); otherwise (company_id, job_id, entity_id). Within a job an
  entity_id keeps its first contact. Each contact lists the `job_ids` that
  touched it; a person without a `full_name` stays per job.
- **change_kind** (`history.py`): `reconfirmed` with the value of a current
  observation of the same contact and field adds no row; that observation
  gets `last_confirmed_at` and a `history` entry `{date, observation_id,
  kind: reconfirmed, value, run_id}`, the new id becomes its alias.
  `supersedes_observation_id` must be an observation of the same contact and
  field (unknown / other contact / other field -> rejected `invalid_input`);
  with `changed` the old one gets `superseded_by` and a `changed` entry.
- **contact.freshness** (`freshness.py`): every check needs a contact of the
  job's company and, when set, an `observation_id` of that contact sent in the
  same run (else `invalid_input`). Applied only with full rights on the current
  run: `reconfirmed` -> contact `last_seen_at`; `changed` -> also a contact
  `history` entry; `not_seen_in_checked_scope` -> `not_seen = {checked_at,
  scope_description, run_id}` (the contact stays; a later sighting clears it);
  `not_checked` -> recorded only. `job.finished.freshness_summary` is stored on
  the run with `freshness_counted` and `freshness_mismatch` (never rejected).
- **known_contacts** in claim (`known.py`): one KnownContact per contact of the
  company touched by another job (unassigned_channel skipped).
  `last_seen_at` = latest observation, reconfirmation or freshness check;
  `channel_status` = strongest of the current channel observations
  (published_direct > published_general > catalog_published > inferred >
  stale), `inferred` without a channel. `fields` as ARGUS answered
  (docs/ANSWERS_S5.md section 1): `{"<field>": "<normalized value>"}`, a list
  of strings (latest first) when there are several; an extra field keyed by
  its `extra_label` (`country`, `department`, `office_name`, `address`);
  addresses in lower case; superseded values left out.
- **extra** (docs/ANSWERS_S5.md sections 2-3): `country`, `department`,
  `office_name`, `address` and `fax` only as `field="extra"` with that
  `extra_label` (a direct field or an `extra` without a label -> event
  rejection `invalid_input`); the quote is checked like every other.
- **Contract 3.1.0 (wire 1.2)**: the heartbeat takes `schema_versions` 1.1 and 1.2
  and keeps the highest common one; a 1.2 events answer carries `detail`
  (`{rule, observation_id, field, message}`, null when accepted), a 1.1 one has no
  key. Rules: `snapshot_missing`, `quote_not_found`, `person_without_name` (a
  `contact.enriched` person without its name). A contact event whose evidence
  was never uploaded is `accepted` + `evidence_pending` (`state_applied=false`, the
  seq is spent) and waits in `pending.py`; the upload of its last evidence applies
  it and its stored result becomes the outcome (ARGUS 0.4.24.4).
- `--state PATH` saves the whole state as JSON after every POST (atomic) and
  loads it at start; evidence bytes and texts go to `PATH.evidence/`.

## Stand-only endpoints (not in the contract, SystemBearer)
`GET /_stand/jobs/{job_id}/contacts` (contacts the job touched with
observations and channel status, recorded rejections, model calls, sources,
`freshness` checks of the job, `freshness_runs` summaries),
`GET /_stand/companies/{company_id}/contacts` (every canonical contact of the
company: observations with `last_confirmed_at` / `superseded_by` / `history`,
`last_seen_at`, `not_seen`, `job_ids`; 404 for a company without jobs) and
`GET /_stand/evidence/{evidence_id}` (metadata + text used for quote checks).

## Layout
`server.py` (start/CLI), `httpio.py`, `routes.py` (auth, dispatch), `context.py`,
`state.py`, `persistence.py`, `schema.py` + `openapi.py`, one module per
endpoint (`batches`, `claim` + `known`, `heartbeat`, `evidence`, `events` with
`event_apply`/`contacts`/`identity`/`history`/`channels`/`freshness`/`finish`,
`reconcile`, `control`, `status`, `stand_views`), `stand.py` (owner CLI), `tests/`.
