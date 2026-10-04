# delivery

The outbox and its thread (TZ_SELAIN 8.13, 10.2; ARGUS20_TZ_TANDEM.md A2.3,
A2.4, A3.1). Entry point: `contract.py`.

| Function / class | What it does |
|---|---|
| `enqueue_event(conn, job, run, make, evidence_ids, seq=None)` | next seq of the run (from the outbox, never reset), new event_id, envelope from the generated event type; no commit: the caller's transaction also holds the observation |
| `enqueue_evidence(conn, local_id, metadata)` | queue a snapshot upload once (`evidence_uploads`) |
| `Deliverer` | thread: pending snapshots first (`upload_evidence`, the exact stored bytes), then per run the leading pending events in seq order that do not wait for a snapshot, <= 50 per request, sent when 50 are ready or the oldest waited 2 s |
| `stats(conn)` | Odottaa lahetysta / Lahetysvirhe / p95 of the last minute |
| `reconcile_info(conn, run)` | last contiguous acknowledged seq, pending event and evidence ids |

Results per event: `accepted` / `duplicate` -> done; `rejected` +
`evidence_missing` -> the snapshot is re-queued and the event retried;
`sequence_gap` -> retried from the first pending seq; any other code ->
`rejected` with the code (shown in Jono). Request errors: no answer ->
`offline` + backoff with jitter; 401/403 -> `delivery_error`; 409
`lease_expired` / `lease_mismatch` / `job_cancelled` -> the scheduler
reconciles (resume or drain-only token) and the next pass retries; 429 ->
`Retry-After`. Nothing is deleted; delivery keeps going after Pysayta / STOP.
`repository.py` owns `outbox` and `evidence_uploads`; `service.py` is pure.
