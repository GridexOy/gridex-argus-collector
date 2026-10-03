# walk

One company-site walk driven by the local model in the visible Chrome
(TZ_SELAIN sections 8.4, 8.5; owner decision 03.10.2026: model + browser
first). Entry point: `contract.run_walk(settings, on_event, should_stop)`.

Loop per page (`runner.py`):
1. `browser.WalkBrowser.goto/click/scroll` -> `PageState` (url, title, html, visible text, numbered candidates).
2. `evidence.store_snapshot` -> html + canonical text on disk, manifest row; `evidence_id` = sha256(html).
3. `extraction.extract_channels` (tel:/mailto:/JSON-LD/cfemail/obfuscated text).
4. When the page has contact signals: model call `walk.cards` -> `extraction.verify_card` on each card; only verbatim-backed fields survive; a verified contact is an `observations` row and an `EVENT_CONTACT`.
5. Model call `walk.action` with the ranked candidates (`discovery.rank_candidates`: approved hosts only, no social networks, unvisited): `navigate <index>` / `click <index>` / `scroll` / `finish`. Invalid answers and model errors fall back to the best-ranked link or finish.
6. Budget: `page_budget` distinct URLs (default 15); a repeated page key (URL + content hash) is not re-parsed; `should_stop()` and the STOP files are checked between steps.

`WalkEvent.kind`: `page`, `step` (`loading`, `extracting`, `model`,
`navigate`, `click`, `scroll`), `contact`, `done`, `stopped`, `error`.
The panel maps them to Finnish lines; the walk itself has no UI strings.

`service.py` is pure (settings, events, prompts, action parsing),
`repository.py` writes `runs` and `observations`, `runner.py` holds the loop.
Tests walk the fixture site with `collector/tests/fake_model_server.py` and
`tests/fake_policy.py` (test doubles) and check every gold person, the
dropped invented person, the quotes against the stored text, the
`model_calls` rows (cost 0) and both stop paths.
