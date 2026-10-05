# walk

One company-site walk in the visible Chrome (TZ_SELAIN 8.4, 8.5). Entry point:
`contract.run_walk(settings, on_event, should_stop, sink=None)`.

Per page (`runner.py` loop, `page.py`, `decide.py`):
1. `enter`: a new URL counts against the page budget; a page state (URL + content
   hash) not seen before is snapshotted (`evidence.store_snapshot`).
2. Channels (`extraction`; phone region from the page, its country section or the
   selected country tab), people read by `cards.py` (0.4.8.0 routing: JSON-LD,
   same text read before, skip when no channel can be a person's and the page is no
   contact page, else the card model `walk.cards`), verified verbatim; DOM binding
   and group heading (`browser.bindings`); findings (`findings.py`, `entities.py`,
   `context.py`, `offices.py`): country / department / office name / address /
   fax as `extra`; local rows + the sink in one transaction.
3. The next step (`decide.py`): `structure.py` (exhibition country of a country
   list; a closed `Worldwide` control; every department tab; other countries'
   controls and, once `/fi-fi/` is reached, other language versions never offered
   while the seed is not local), then `rules.py` (exhibition-country version, the
   country finder, a contact link by its words), the menu cache, the vision model
   for a page without DOM text (`vision.py`), else the navigation model (7b; the
   card model once it fails). No finish while a strong link is unvisited.
4. A bot check that does not clear in 20 s ends the walk as `attention` (gap
   `captcha`); one sign only: the vision model looks first, never solves it. A
   failed action is a gap and the walk goes on; three in a row end it. Relevant
   links left at the end are gaps (`budget_reached` / `no_progress`); own-brand
   links outside approved_hosts are `domain_ownership_unresolved` (`coverage.py`).
5. `timing.py`: one journal line per page state, `browser: job <id>: timing <url>
   load= snapshot= extract= cards= bind= record= action= decide= reader=` (ms;
   who decided, who read the cards) for `pilot timing`.

Job mode (`WalkSettings.approved_hosts/limits/focus/resume/id_namespace`): job
hosts, run budget, stable ids, a checkpoint after every page and resume from it.
`WalkSettings.model` reads cards, `navigation` chooses steps, `vision` looks at
screenshots. `WalkSummary.end_reason`: finished / budget / stopped / error /
attention / domain_unresolved / start_failed / action_failures. The sink
(`sink.py`, implemented by `scheduler`) gets `page_stored`, `page_done`, `gap`,
`model_called`, `checkpoint`. Tests: fixture site + fake model.
