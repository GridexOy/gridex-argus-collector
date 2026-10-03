# browser

Playwright driver of the work browser. Entry point: `contract.py`.

| Function | What it does |
|---|---|
| `plan_for_this_machine(headless, profile_dir)` | `LaunchPlan`: installed Chrome (`channel="chrome"`) on Windows, bundled Chromium elsewhere; profile `<user_data_dir>/browser-profile` |
| `open_work_browser(url, ...)` | S0: opens the visible window on a URL, returns `LaunchResult`; raises `BrowserLaunchError` with one English line |
| `launcher_command(url, serve_test_site_port)` | argv for the detached launcher `python -m argus_collector.browser` ("Avaa tyoselain") |
| `WalkBrowser(headless, profile_dir)` | context manager of a walk (`session.py`): one persistent-profile context, one tab; `goto(url)`, `click(candidate)`, `scroll()`, `observe()` return `PageState(url, title, html, text, candidates)` |

`PageState.candidates` are the visible, enabled links (`a[href]` with an
http(s) href, acted on by navigation) and buttons (`button`, `role=button`,
`summary`, links without http href, acted on by click). `mailto:`/`tel:`
links are values, not actions (TZ section 8.4); submit buttons are never
pressed (no forms in this step). Each element gets `data-argus-idx="<n>"`
so the model's chosen index is clicked exactly. Readiness: DOM content +
`load` (10 s cap) + 0.8 s settle; navigation timeout 45 s (section 8.5).

`service.py` holds the decisions (channel, args, failure text);
`repository.py` and `session.py` are the only files that import Playwright.
The installed Chrome needs no `playwright install`; the bundled Chromium is
used only on non-Windows machines (CI, this container). The walk and
"Avaa tyoselain" share the profile, so only one of them runs at a time.
