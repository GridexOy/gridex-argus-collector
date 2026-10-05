# pilot

The collector side of the pilot report (ARGUS20_TZ_TANDEM.md pair 5, §9:
time per company, pages and actions, model calls; the 10-phone check).
Entry point: `contract.py`; command line `python -m argus_collector.pilot
[--batch ID] [--out FILE] [--sample 10] [--seed 5] [--db PATH]`.

| Part | What it does |
|---|---|
| `contract.report(conn, batch_id)` | one batch (the latest when None) from the local SQLite: a `CompanyRow` per job, a random sample of phone observations checked |
| `CompanyRow` | result and reason, active and wall minutes (job.finished), pages, browser actions, model calls / tokens / seconds (model.called), persons, channels, `published_direct` among the contact events ARGUS rated, whether a person has a channel that is not inferred / stale |
| `PhoneCheck` | the snapshot behind the observation: its host is in the job's approved_hosts, the quote is at its `text_span` (or in the snapshot text / html) |
| `PilotReport.threshold_met` | >= 50 % of the companies have such a person (BLOCKS block 6) |
| `render_markdown` | the two tables for `docs/ARGUS20_COLLECTOR_STAGE6_REPORT.md` |
| `timing_markdown(lines, names, source)` | 0.4.8.0 (`timing.py`, `timing_render.py`): a collecting day's journal per company: page phases (load, snapshot, extract, cards, bind, record, next step), who decided (rules / each model / cache / fallback), model calls (model, purpose, ms, tokens), delivery; `python -m argus_collector.pilot timing --log FILE [--out FILE]`, `scripts\walk_timing.ps1` |
| `rejected_markdown(conn)` | 0.4.8.1 (`rejected.py`): every event and snapshot ARGUS rejected: time, company, job, kind, event_id / evidence_id, seq, code, words; `python -m argus_collector.pilot rejected [--out FILE]`, `scripts\delivery_check.ps1` |

No tables of its own: jobs from `scheduler.job_facts`, events and ARGUS's
answers from `delivery.run_results`, snapshots from `evidence`. Gold P / R,
Nimetty henkilö and Soitettavia are ARGUS screens, not computed here.
Tests: `tests/` run a batch against `contract_server/` and the fixture site.
