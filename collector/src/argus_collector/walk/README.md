# walk

One company-site walk in the visible Chrome (TZ_SELAIN 8.4, 8.5). Entry point:
`contract.run_walk(settings, on_event, should_stop, sink=None)`.

Per page (`runner.py` loop, `page.py`, `decide.py`):
1. `enter`: a new URL counts against the page budget; a page state (URL + content
   hash) not seen before is snapshotted (`evidence.store_snapshot`).
2. People (`cards.py`): JSON-LD, the rules (`extraction.text_cards`), the same text
   read before; only when they read nobody, the card model `walk.cards` in windows
   around the person-like channels, on worker threads while the next step is chosen;
   all read before any navigation. A pattern the page states gives its people without
   an email an unconfirmed address quoted from that line, plus the company's
   `email_pattern` (`patterns.py`, 0.4.8.6). Findings (`findings.py`, `entities.py`,
   `context.py`, `offices.py`); local rows + the sink in one transaction.
3. The goal (`goal.py`, `ending.py`, owner 06.10.2026), asked before every next action:
   a sales / marketing person with a printed channel ends the walk `goal`; people
   without it allow 2 more pages (`goal_pages`); off: `stop_at_goal=False`.
4. The next step (`decide.py`): `structure.py` (country list, `Worldwide`, department
   tabs), `rules.py` (country version, country finder, contact link), the menu cache;
   on a page the rules read: the best-ranked link, never a model; else the vision
   model for a page without DOM text (`vision.py`) or the navigation model (7b).
   An unvisited link is no reason not to finish.
5. No circles (0.4.8.6): a link that led elsewhere on the hosts (a redirect) is walked; a
   page read before is never the target; a button pressed in a page state is not
   offered again; a state repeated 3 times finishes its branch; 6 actions without a
   new state end the walk `no_progress`; the panel's walk has `action_budget` (60).
6. A bot check that does not clear in 20 s ends the walk as `attention` (gap
   `captcha`); failed actions are gaps, three in a row end it; relevant links left
   are gaps (`budget_reached` / `no_progress`, `coverage.py`).
7. `timing.py`: `browser: job <id>: timing <url> load= ... decide= reader=` per page
   state and `chrome start=<ms> ms shared=` per walk, for `pilot timing`.

Job mode (`WalkSettings.approved_hosts/limits/focus/resume/id_namespace`): job hosts,
run budget, stable ids, a checkpoint after every page. `browser_host`: the
collection's Chrome, a clean context per walk (a resume after a bot check uses the
work-browser profile). `WalkSummary.end_reason`: finished / goal / goal_pages /
budget / no_progress / stopped / error / attention / domain_unresolved /
start_failed / action_failures. The sink (`sink.py`, implemented by `scheduler`)
gets `page_stored`, `page_done`, `gap`, `model_called`, `checkpoint`.
