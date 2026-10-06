# delivery

The outbox and its thread (TZ_SELAIN 8.13, 10.2; ARGUS20_TZ_TANDEM.md A2.3,
A2.4, A3.1). Entry point: `contract.py`.

| Function / class | What it does |
|---|---|
| `enqueue_event(conn, job, run, make, evidence_ids, seq=None)` | next seq of the run (from the outbox, never reset), new event_id, envelope from the generated event type; no commit: the caller's transaction also holds the observation |
| `enqueue_evidence(conn, local_id, metadata)` | queue a snapshot upload once (`evidence_uploads`) |
| `Deliverer` | two threads (0.4.8.7, WINLOG 06.10): events per run in seq order, <= 50 per request, sent when a page's closing event is written, 50 are ready or the oldest waited 2 s (polled every 0.2 s); snapshots on their own (`uploads.py`, the exact stored bytes). An event does not wait for its snapshot (contract 3.1.0: ARGUS keeps it `evidence_pending`); one refused `evidence_missing` waits for it |
| `Deliverer.link(answered)` | heartbeat outcome: no answer -> `offline` also with an empty outbox; the first answer after it sends at once; 0.4.8.2 (`transport.py`): the one state of Lahetys: `offline` only when the heartbeat got no answer and delivery got none either (last request, or none answered since the heartbeat went down); a delivery request without an answer alone is a retry; each change is journaled once |
| `stats(conn)` | Odottaa lahetysta / Lahetysvirhe / p95 of the last minute (0.4.8.6: events queued and acknowledged within it; one that waited in the queue from before is not counted); `last_code` of the latest rejection |
| `rejections(conn)`, `reason(code)` | 0.4.8.1: every rejected event / snapshot (job, id, seq, code), latest first; English words for a code (`http_<status>` for an answer without an error body) |
| `reconcile_info(conn, run)` | last contiguous acknowledged seq, pending event and evidence ids |

Results per event: `accepted` / `duplicate` -> done; `rejected` +
`evidence_missing` -> `retry.py` (0.4.8.5): the snapshot is uploaded again first,
at most 3 retries with that code; a snapshot not stored here or a 4th refusal
gives the event up (`todiste puuttuu`, counted, never sent again) and a
`source.blocked` stand-in takes its free seq; `sequence_gap` -> retried from the
first pending seq, not counted; any other code ->
`rejected` with the code (shown in Jono); wire 1.2: the code is stored as
`<code>/<rule>` and the rule's words are shown; an event whose snapshot was lost or
refused here is given up before it is sent (`retry.lost`). Request errors: no answer ->
backoff with jitter (`offline` only with the heartbeat, `transport.py`); 401/403 -> `delivery_error`; 409
`lease_expired` / `lease_mismatch` / `job_cancelled` -> the scheduler
reconciles (resume or drain-only token) and the next pass retries; 429 ->
`Retry-After`. Nothing is deleted; delivery keeps going after Pysayta / STOP.
Journal (0.4.8.1): a request error is `HTTP <status> <code> (<words>) request_id=<id>`
(ARGUS's detail is not written: it may quote a contact value); every rejected
item is one line with the company, `event <event_id> seq <n>` or `evidence <id>`,
the code and its words; a 5xx shows `Palvelinvirhe: <status>` until a pass gets through.
`results.py` writes one events answer back; `repository.py` owns `outbox` and
`evidence_uploads`; `service.py` is pure.

0.4.8.8 (owner 06.10.2026): nothing leaves the outbox but accepted / duplicate. A
request refused as a whole (4xx, 409 lease) holds its run (`holds.py`, backoff; the
other runs go on); a snapshot is refused for good only for the file itself; a pass
that raises is journaled and retried, a lane that ended is started again.
