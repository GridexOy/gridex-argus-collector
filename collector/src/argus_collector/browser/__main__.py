"""Detached launcher: `python -m argus_collector.browser --url URL [options]`.

Opens the visible work browser and exits when its last window is closed.
With `--serve-test-site PORT` it also serves `test_site/` from the source
tree for as long as it runs (a busy port means the site is already up).
Exit codes: 0 opened and closed normally, 2 browser failed, 3 bad arguments.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from argus_collector.browser import contract
from argus_collector.browser.service import LaunchResult
from argus_collector.runtime import contract as runtime


def _serve_test_site(port: int) -> object | None:
    sys.path.insert(0, str(runtime.repo_root()))
    from test_site import server  # noqa: PLC0415 - optional, source tree only

    try:
        return server.start(port=port)
    except OSError as exc:
        print(f"test site not started on port {port} ({exc}); assuming it is up", flush=True)
        return None


def _announce(result: LaunchResult) -> None:
    payload = {
        "opened": True,
        "url": result.url,
        "title": result.title,
        "profile": str(result.user_data_dir),
        "browser": result.browser_version,
    }
    print(json.dumps(payload), flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Open the ARGUS collector work browser")
    parser.add_argument("--url", required=True)
    parser.add_argument("--serve-test-site", type=int, metavar="PORT", default=None)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--no-wait", action="store_true", help="exit right after the page opened")
    parser.add_argument("--profile-dir", type=Path, default=None)
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return 3
    if args.serve_test_site is not None:
        _serve_test_site(args.serve_test_site)
    try:
        contract.open_work_browser(
            args.url,
            headless=args.headless,
            wait_until_closed=not args.no_wait,
            profile_dir=args.profile_dir,
            on_open=_announce,
        )
    except contract.BrowserLaunchError as exc:
        print(str(exc), file=sys.stderr, flush=True)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
