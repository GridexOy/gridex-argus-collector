# walk

One company-site walk: the local model drives the visible Chrome (TZ_SELAIN
8.4, 8.5). Entry point: `contract.run_walk(settings, on_event, should_stop, sink=None)`.

Per page (`runner.py` loop, `page.py`, `decide.py`):
1. `enter`: a new URL counts against the page budget; `observe`: a page state
   (URL + content hash) not seen before is snapshotted (`evidence.store_snapshot`).
2. Channels (`extraction.extract_channels`, phone region from the page), model
   cards (`walk.cards`) verified verbatim, DOM binding of each field
   (`browser.bindings`, job mode), findings (`findings.py`): persons
   new/enriched, unclaimed channels as organization / office / unassigned,
   the page's field audit; local `observations` rows + the sink in one transaction.
3. Links of the page join a frontier of the whole site; the model (`walk.action`,
   with the job's country focus brief) picks from the page's links, frontier
   links and buttons; invalid answers fall back to the best link. In job mode
   the model may not finish while a link scoring >= 10 is unvisited.
4. A failed action is a gap (`timeout` / `network_error` / `unsupported_widget`)
   and the walk goes on; three in a row end it. A navigation is retried once.

Job mode (`WalkSettings.approved_hosts/limits/focus/resume/id_namespace`,
ARGUS20_TZ_TANDEM.md A2): hosts from the job, a seed landing elsewhere is gap
`domain_ownership_unresolved` and ends the walk, budget = pages / actions /
active seconds / states of the run, ids stable within the job, checkpoint after
every page (visited, seen states, frontier, entities, observation ids, counters),
resume from it after a restart, a stop or a lost lease (tabs are not restored).
`WalkSummary.end_reason`: finished / budget / stopped / error /
domain_unresolved / start_failed / action_failures.

The sink (`sink.py`, implemented by `scheduler`) gets `page_stored`,
`page_done` (inside the walk's transaction), `gap`, `model_called`, `checkpoint`.
A panel walk has no sink and keeps everything local (0.4.1.x behaviour).
Tests: fixture site + `collector/tests/fake_model_server.py` with
`tests/fake_policy.py` (GoldPolicy, RankedPolicy), job mode in `test_walk_job.py`.
