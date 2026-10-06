"""One Chrome for a whole collection, a fresh context per company (owner 06.10.2026).

Starting Chrome for every company cost seconds per walk (MAIN-PC 05.10.2026:
a restart per company). The collecting thread now keeps one browser
(`BrowserHost`): each company's walk gets a new context - clean cookies and
storage - which is closed after the walk; the browser stays until collecting
ends. A browser that died is started again for the next walk. Playwright's
sync API belongs to the thread that started it, so the host is opened, used
and closed in the collecting thread only. `launch_persistent` is the old way
(the work-browser profile), kept for the panel's local test and for a walk
that resumes after the owner passed a bot check in the work browser (its
cookies are in that profile): with a host, that profile is opened by the
host's own Playwright (`profile_context`; a second sync Playwright in the same
thread fails). Both report the start in milliseconds.
"""

from __future__ import annotations

import time
from pathlib import Path

from playwright.sync_api import Browser, BrowserContext, Playwright, sync_playwright

from argus_collector.browser.service import (
    ACCEPT_LANGUAGE,
    CONTEXT_ONLY,
    TIMEZONE,
    LaunchPlan,
    launch_kwargs,
)


def _plan(headless: bool, profile_dir: Path | None) -> LaunchPlan:
    from argus_collector.browser import contract  # noqa: PLC0415 - avoid import cycle

    return contract.plan_for_this_machine(headless=headless, profile_dir=profile_dir)


def launch_persistent(headless: bool, profile_dir: Path | None, pw: Playwright | None = None
                      ) -> tuple[Playwright, BrowserContext, int]:
    """(playwright, the profile's context, start ms): Chrome on the work-browser profile,
    started by `pw` when given, else by a Playwright of its own."""
    plan = _plan(headless, profile_dir)
    plan.user_data_dir.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    pw = pw or sync_playwright().start()
    context = pw.chromium.launch_persistent_context(**launch_kwargs(plan))  # type: ignore[arg-type]
    return pw, context, int((time.monotonic() - started) * 1000)


class BrowserHost:
    """`host.context()` per company; `host.close()` when collecting ends."""

    def __init__(self, headless: bool, profile_dir: Path | None = None) -> None:
        self.headless, self.profile_dir = headless, profile_dir
        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        self.starts = 0  # browser starts of this collection
        self.start_ms = 0  # their milliseconds in total

    @property
    def running(self) -> bool:
        return self._browser is not None and self._browser.is_connected()

    def context(self) -> tuple[BrowserContext, int]:
        """(a new context with clean cookies, ms spent starting the browser for it: 0
        when the browser was already running)."""
        launched = 0 if self.running else self._launch()
        assert self._browser is not None
        context = self._browser.new_context(
            no_viewport=True, timezone_id=TIMEZONE,
            extra_http_headers={"Accept-Language": ACCEPT_LANGUAGE})
        return context, launched

    def profile_context(self) -> tuple[BrowserContext, int]:
        """The work-browser profile in a Chrome of its own, closed with the context."""
        self._pw = self._pw or sync_playwright().start()
        _pw, context, elapsed = launch_persistent(self.headless, self.profile_dir, self._pw)
        self.starts += 1
        self.start_ms += elapsed
        return context, elapsed

    def _launch(self) -> int:
        self._drop_browser()  # it died: a new one, the same Playwright
        kwargs = launch_kwargs(_plan(self.headless, self.profile_dir))
        for key in ("user_data_dir", "no_viewport", *CONTEXT_ONLY):
            kwargs.pop(key)
        started = time.monotonic()
        self._pw = self._pw or sync_playwright().start()
        self._browser = self._pw.chromium.launch(**kwargs)  # type: ignore[arg-type]
        elapsed = int((time.monotonic() - started) * 1000)
        self.starts += 1
        self.start_ms += elapsed
        return elapsed

    def _drop_browser(self) -> None:
        try:
            if self._browser is not None:
                self._browser.close()
        except Exception:  # noqa: BLE001 - closing never hides what collecting did
            pass
        self._browser = None

    def close(self) -> None:
        self._drop_browser()
        try:
            if self._pw is not None:
                self._pw.stop()
        except Exception:  # noqa: BLE001 - closing never hides what collecting did
            pass
        self._pw = None


def open_context(host: BrowserHost | None, profile: bool, headless: bool,
                 profile_dir: Path | None) -> tuple[Playwright | None, BrowserContext, int]:
    """(own Playwright to stop or None, the walk's context, Chrome start ms): a clean context
    of the host's Chrome, else the work-browser profile (by the host's Playwright)."""
    if host is not None and not profile:
        return (None, *host.context())
    if host is not None:
        return (None, *host.profile_context())
    return launch_persistent(headless, profile_dir)
