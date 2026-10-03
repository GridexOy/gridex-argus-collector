"""Playwright calls of the browser module (the only file that imports it)."""

from __future__ import annotations

from collections.abc import Callable

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from argus_collector.browser.service import (
    LaunchPlan,
    LaunchResult,
    describe_failure,
    launch_kwargs,
)

NAVIGATION_TIMEOUT_MS = 15_000


class BrowserLaunchError(RuntimeError):
    """The work browser could not be started or the page could not be opened."""


def open_persistent(
    plan: LaunchPlan,
    url: str,
    wait_until_closed: bool,
    on_open: Callable[[LaunchResult], None] | None = None,
) -> LaunchResult:
    """Open `url` in a persistent profile; optionally block until the window closes."""
    plan.user_data_dir.mkdir(parents=True, exist_ok=True)
    try:
        with sync_playwright() as pw:
            context = pw.chromium.launch_persistent_context(**launch_kwargs(plan))  # type: ignore[arg-type]
            try:
                page = context.pages[0] if context.pages else context.new_page()
                page.goto(url, timeout=NAVIGATION_TIMEOUT_MS)
                result = LaunchResult(
                    url=page.url,
                    title=page.title(),
                    user_data_dir=plan.user_data_dir,
                    browser_version=context.browser.version if context.browser else "",
                )
                if on_open is not None:
                    on_open(result)
                if wait_until_closed:
                    context.wait_for_event("close", timeout=0)
            finally:
                _close_quietly(context.close)
    except (PlaywrightError, OSError) as exc:
        raise BrowserLaunchError(describe_failure(plan, exc)) from exc
    return result


def _close_quietly(close: Callable[[], None]) -> None:
    try:
        close()
    except PlaywrightError:
        pass
