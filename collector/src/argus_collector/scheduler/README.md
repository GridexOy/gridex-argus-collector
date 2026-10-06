# scheduler

ARGUS jobs on this PC (ARGUS20_TZ_TANDEM.md pairs A2, A3; TZ_SELAIN 8.1,
8.6, 8.10, 8.14). Entry point: `contract.Collector`.

| File | Role |
|---|---|
| `collector.py` | `Collector.start()` (Kaynnista) / `stop()` (Pysayta); the collecting thread: next runnable job -> walk, waiting jobs -> reconcile, free slots -> `claim_jobs` (max 8, every 10 s); 0.4.8.6: one Chrome (`browser.BrowserHost`) for the whole collection, closed when it stops |
| `hooks.py` | answers to `delivery` (token of a run, lease problem -> reconcile, rejected -> Jono counter, ARGUS job state `paused` / `cancelled` in an events answer -> interrupt after the current page) and to the heartbeat loop (`heartbeat_fields`, `apply_heartbeat`); interrupts of the running walk |
| `leases.py` | ClaimedJob -> `jobs` row (same run = lease renewal, new run = reset), heartbeat fields, lease renewals, commands (recorded once, acked next heartbeat; repeated = `already_applied`), `reconcile_job` |
| `runner.py` | one run: `job.started` once, the walk with the job's seed, `approved_hosts`, budget (policy minus campaign use), country focus, resume checkpoint; `job.finished` once |
| `sink.py` | `walk.WalkSink`: snapshot -> evidence upload; findings -> `contact.observed` / `contact.enriched` + `source.processed` in the walk's transaction; gaps -> `source.blocked`; model calls -> `model.called`; checkpoint row + `job.progress` every 15 s |
| `events.py`, `finish.py` | payloads with the generated `api_client` types: observation (locator `text_span` / `json_pointer` / `dom`, quote, binding, extraction_status; country / department / office_name / address / fax as `field="extra"` + `extra_label`, audit `extra`, 0.4.7.0), field audit, counts, coverage (`unverified` without a catalog total), gaps, server checkpoint, budget, models per purpose |
| `history.py`, `freshness.py` | 0.4.5.0 (A4): known contacts of a re-run (`ClaimedJob.known_contacts`, any value shape) -> `change_kind` `new` / `reconfirmed` / `changed` + `supersedes_observation_id` per observation; at the end of the run one `contact.freshness` check per field of every known contact (reconfirmed / changed / not_seen_in_checked_scope when the frontier was exhausted / not_checked), before `job.finished`, whose `freshness_summary` counts them |
| `views.py` | Jono rows and Lahetys line from the local SQLite |
| `repository.py` | tables `jobs`, `checkpoints`, `entity_map`, `commands` |
| `service.py` | pure: local states, run budget, outcome (`run_result_status`, `completion_reason`; the walk's goal ends `completed`), purposes |

Local job states: `queued` -> `running` -> `completed` / `partial` / `failed` /
`cancelled`; `stopped` (Pysayta, STOP, panel closed: resumes on Kaynnista),
`paused` (ARGUS pause), `waiting_lease` (lease expired or mismatched:
reconcile before walking), `needs_attention` (0.4.4.0: a bot check did not
clear; `job.needs_attention` with the gap, the lease stays renewed, no walk
while the owner's work browser is open; Huomio "Jatka kasin tehdyn toimen
jalkeen" or ARGUS resume -> `queued`, the run goes on from that URL). A walk is interrupted between steps by
Pysayta/STOP, pause, cancel or a lease that expired locally; cancel ends the
run with `job.finished` `cancelled` / `manual_cancel`, the others keep it
resumable. After a restart `running` jobs become `stopped`; seq, entity and
observation ids come from SQLite, so nothing is sent twice.

Tests (`tests/`) run the collector headless against `contract_server/`, the
fixture site and the fake model.
