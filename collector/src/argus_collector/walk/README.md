# walk

One company-site walk in the visible Chrome (TZ_SELAIN 8.4, 8.5). Entry point:
`contract.run_walk(settings, on_event, should_stop, sink=None)`.

0. The country's version first (`country.py`, 0.4.8.7): a first page that is another
   country's version goes to the exhibition country's one before anything is read
   (`discovery.version_candidates`, asked by `browser.probe`); step `country`.
Per page (`runner.py` loop, `page.py`, `decide.py`):
1. `enter`: a new URL counts against the page budget; a page state (URL + content
   hash) not seen before is snapshotted. K7 (`scope.py`): a page outside the company's
   domains (`company_domains`) is a source only, nobody and no channel is read.
2. People (`cards.py`): JSON-LD, the rules (`extraction.text_cards`), the same text
   read before; only when they read nobody, the card model in windows around the
   person-like channels, on worker threads; all read before any navigation. A stated
   pattern gives unconfirmed addresses (`patterns.py`). Findings (`findings.py`,
   `entities.py`: the name in every person event; `context.py`: country = section,
   phone code, `lang`; `offices.py`); local rows + the sink in one transaction.
3. The goal (`goal.py`, `ending.py`), asked before every next action: a sales /
   marketing person with a printed channel ends the walk `goal` after the found team /
   contact links (<= 2) are read; people without it allow 2 more pages (`goal_pages`).
4. The next step (`decide.py`): `structure.py` (country list, `Worldwide`, department
   tabs), `rules.py` (country version, country finder, contact link), the menu cache;
   on a page the rules read: the best-ranked link, never a model; else the vision
   model for a page without DOM text (`vision.py`) or the navigation model.
5. No circles: a link that led elsewhere (a redirect) is walked; a page read before is
   never the target; a pressed button is not offered again; a state repeated 3 times
   finishes its branch; 6 actions without a new state end the walk `no_progress`.
6. A bot check that does not clear in 20 s ends the walk as `attention` (gap
   `captcha`); failed actions are gaps, three in a row end it; relevant links left
   are gaps (`budget_reached` / `no_progress`, `coverage.py`).
7. `timing.py`: a `timing` journal line per page state, `chrome start=` per walk.

Job mode (`WalkSettings.approved_hosts/limits/focus/resume/id_namespace`): job hosts,
run budget, stable ids, a checkpoint after every page; `browser_host`: the
collection's Chrome, a clean context per walk. `WalkSummary.end_reason`: finished /
goal / goal_pages / budget / no_progress / stopped / error / attention /
domain_unresolved / start_failed / action_failures. The sink (`sink.py`, implemented
by `scheduler`) gets `page_stored`, `page_done`, `gap`, `model_called`, `checkpoint`.
