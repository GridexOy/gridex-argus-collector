# browser

Playwright driver of the work browser. Entry point: `contract.py`.

| Function | What it does |
|---|---|
| `plan_for_this_machine(headless, profile_dir)` | `LaunchPlan`: installed Chrome (`channel="chrome"`) on Windows, bundled Chromium elsewhere; profile `<user_data_dir>/browser-profile` |
| `open_work_browser(url, ...)` | S0: opens the visible window on a URL, returns `LaunchResult`; raises `BrowserLaunchError` with one English line |
| `launcher_command(url, serve_test_site_port)` | argv for the detached launcher `python -m argus_collector.browser` ("Avaa tyoselain") |
| `WalkBrowser(headless, profile_dir, host)` | context manager of a walk (`session.py`): one context, one tab; `goto(url)`, `click(candidate)`, `scroll()`, `back()`, `observe()` return `PageState(url, title, html, text, candidates)`; `start_ms`: the Chrome start of this walk |
| `BrowserHost(headless)` | 0.4.8.6 (`host.py`, owner 06.10.2026): one Chrome for a whole collection; `context()` gives each company a new context (clean cookies), closed after its walk; started again when it died; without a host the walk opens the work-browser profile (panel test, resume after a bot check) |
| `WalkBrowser.bindings(probes)` | 0.4.3.0 (`binding.py`): DOM binding of each verified person field: `card` / `table_row` (name and value meet in a small container with no other person) / `proximity_only` / `none` (TZ_SELAIN 8.11, 9.4); 0.4.4.0: plus the person's group (nearest heading before the card in its tab panel / section, else its tab label) |
| `PageState.consent` | 0.4.6.0 (`page_tools.py`): a cookie banner is answered once per host before the page is read: necessary cookies, else reject, accept only when nothing else (TZ_SELAIN 8.5); the choice is journaled |
| `PageState.tab_panels` / `challenge_hint`, `screenshot()`, `wait_out_challenge()` | 0.4.8.0: the selected tabs with their panel text (a `Germany` tab is that country's section); one bot-check sign only (the vision model may look); a JPEG of the view; a check the vision model saw, waited out for 20 s |
| `WalkBrowser.select(candidate, option)`, `PageState.challenge` | 0.4.4.0 (`scripts.py`): tabs, accordion headers (`aria-expanded`, `summary`) and dropdowns are candidates; a bot check (two of: title, text, challenge element; short page) is waited out for up to 20 s, still there -> `challenge=True` |

`PageState.candidates` are the visible, enabled links (`a[href]` with an
http(s) href, acted on by navigation) and buttons (`button`, `role=button`,
`summary`, links without http href, acted on by click). `mailto:`/`tel:`
links are values, not actions (TZ section 8.4); submit buttons of a form are
never pressed (no forms in this step). Each element gets `data-argus-idx="<n>"`
so the model's chosen index is clicked exactly. Readiness: DOM content +
`load` (10 s cap) + a quiet DOM (0.4.8.0: 300 ms without a mutation, 0.8 s at most,
once; it was a fixed 2 x 0.8 s); navigation timeout 45 s (section 8.5).

`service.py` holds the decisions (channel, args, failure text);
`repository.py`, `session.py` and `host.py` are the only files that import Playwright.
The installed Chrome needs no `playwright install`; the bundled Chromium is
used only on non-Windows machines (CI, this container). The walk and
"Avaa tyoselain" share the profile, so only one of them runs at a time.

0.4.8.7: every context is fi-FI whatever Windows says (K10 step 1: `--lang`,
`--accept-lang`, `Accept-Language: fi,sv;q=0.8,en;q=0.6`, `Europe/Helsinki`); the
page text is read with CSS `text-transform` off (names as the HTML writes them);
`probe(wb, url)` gives status and final URL without leaving the page; clicks wait 3 s.
