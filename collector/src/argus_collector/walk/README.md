# walk

One company-site walk: the local model drives the visible Chrome (TZ_SELAIN
8.4, 8.5). Entry point: `contract.run_walk(settings, on_event, should_stop, sink=None)`.

Per page (`runner.py` loop, `page.py`, `decide.py`):
1. `enter`: a new URL counts against the page budget; `observe`: a page state
   (URL + content hash) not seen before is snapshotted (`evidence.store_snapshot`).
2. Channels (`extraction.extract_channels`, phone region from the page or its
   country section), model cards (`walk.cards`) verified verbatim, DOM binding
   and group heading of each person (`browser.bindings`, job mode), findings
   (`findings.py`, `entities.py`): persons with department and country
   (`context.py`), the office of each opened country section (`offices.py`),
   other channels as organization / office / unassigned, the field audit;
   local `observations` rows + the sink in one transaction.
3. `structure.py` first (owner 05.10.2026): on a country list only the
   exhibition country is opened / selected, the others are not offered; every
   department tab is opened, sales and marketing first. Then links join a
   frontier of the whole site and the model (`walk.action`, focus brief) picks;
   in job mode it may not finish while a strong link (`discovery.strong_link`)
   is unvisited. A bot check that does not clear in 20 s ends the walk as
   `attention` (gap `captcha`, resumes on that URL).
4. A failed action is a gap (`timeout` / `network_error` / `unsupported_widget`)
   and the walk goes on; three in a row end it (`actions.py`). Every relevant
   link left when the budget or the failures end the walk is a gap
   (`budget_reached` / `no_progress`); own-brand relevant links on hosts
   outside approved_hosts are gaps `domain_ownership_unresolved`; a directory
   that states its size gives the expected count (`coverage.py`, A4.3).

Job mode (`WalkSettings.approved_hosts/limits/focus/resume/id_namespace`, TANDEM
A2): hosts from the job (a seed landing elsewhere: gap `domain_ownership_unresolved`,
end), run budget, ids stable within the job, checkpoint after every page, resume
from it after a restart, a stop or a lost lease (tabs are not restored).
`WalkSummary.end_reason`: finished / budget / stopped / error / attention /
domain_unresolved / start_failed / action_failures.

The sink (`sink.py`, implemented by `scheduler`) gets `page_stored`, `page_done`
(inside the walk's transaction), `gap`, `model_called`, `checkpoint`; a panel walk
has no sink. Tests: fixture site + fake model (`tests/fake_policy.py`).
