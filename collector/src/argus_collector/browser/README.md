# browser

Playwright driver of the work browser. S0 scope: open a visible window
with the persistent profile on a URL (test card section 13.1 row 3). Actions,
readiness, obstacles and routes arrive in S3.

Entry point: `contract.py`.

| Function | What it does |
|---|---|
| `plan_for_this_machine(headless, profile_dir)` | `LaunchPlan`: installed Chrome (`channel="chrome"`) on Windows, bundled Chromium elsewhere; profile `<user_data_dir>/browser-profile` |
| `open_work_browser(url, headless, wait_until_closed, profile_dir, on_open)` | `launch_persistent_context`, `goto(url)`, returns `LaunchResult(url, title, user_data_dir, browser_version)`; raises `BrowserLaunchError` with one English line |
| `launcher_command(url, serve_test_site_port)` | argv for the detached launcher `python -m argus_collector.browser` |

`__main__.py` is the launcher the panel starts: it optionally serves
`test_site/` from the source tree, prints one JSON line
`{"opened": true, ...}` when the page is open and exits when the last browser
window closes (exit 2 on failure, error on stderr).

`service.py` holds the decisions (channel, args, failure text), `repository.py`
is the only file that imports Playwright. The installed Chrome needs no
`playwright install`; the bundled Chromium is used only on non-Windows
machines (CI, this container).
