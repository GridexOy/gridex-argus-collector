"""Single entry point of the `browser` module.

Open the visible work browser (persistent profile, installed Chrome on
Windows) on a URL, give the panel a command line that does the same in a
separate process, and drive a walk page by page (`WalkBrowser`, `session.py`).
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from pathlib import Path

from playwright.sync_api import Error as ActionError

from argus_collector.browser import repository, service
from argus_collector.browser.binding import PersonBinding, PersonProbe, ProbeValue
from argus_collector.browser.repository import BrowserLaunchError
from argus_collector.browser.service import LaunchPlan, LaunchResult
from argus_collector.browser.session import PageState, WalkBrowser
from argus_collector.runtime import contract as runtime

__all__ = [
    "ActionError",
    "BrowserLaunchError",
    "LaunchPlan",
    "LaunchResult",
    "PageState",
    "PersonBinding",
    "PersonProbe",
    "ProbeValue",
    "WalkBrowser",
    "launcher_command",
    "launcher_env",
    "open_work_browser",
    "plan_for_this_machine",
]

LAUNCHER_MODULE = "argus_collector.browser"
SOURCE_DIR = Path("collector") / "src"


def plan_for_this_machine(headless: bool = False, profile_dir: Path | None = None) -> LaunchPlan:
    return service.launch_plan(
        profile_dir=profile_dir or runtime.browser_profile_dir(),
        windows=os.name == "nt",
        headless=headless,
    )


def open_work_browser(
    url: str,
    headless: bool = False,
    wait_until_closed: bool = True,
    profile_dir: Path | None = None,
    on_open: Callable[[LaunchResult], None] | None = None,
) -> LaunchResult:
    """Open `url` in the work browser. Raises BrowserLaunchError with an English line."""
    plan = plan_for_this_machine(headless=headless, profile_dir=profile_dir)
    return repository.open_persistent(plan, url, wait_until_closed, on_open)


def launcher_command(url: str, serve_test_site_port: int | None = None) -> list[str]:
    """Command for a detached process: `python -m argus_collector.browser ...`."""
    cmd = [sys.executable, "-m", LAUNCHER_MODULE, "--url", url]
    if serve_test_site_port is not None:
        cmd += ["--serve-test-site", str(serve_test_site_port)]
    return cmd


def launcher_env() -> dict[str, str]:
    """Environment for the launcher: the source tree first on PYTHONPATH.

    Works both from the installed copy (package installed in the venv) and
    from a plain checkout where nothing is installed.
    """
    env = dict(os.environ)
    source = str(runtime.repo_root() / SOURCE_DIR)
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = source if not existing else source + os.pathsep + existing
    return env
