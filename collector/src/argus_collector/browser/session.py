"""Playwright page session of a walk (the second file that imports Playwright).

`WalkBrowser` keeps one context and one tab: a new context of the collection's
Chrome (`host.py`, clean cookies, closed after the walk) or the work-browser
profile's own Chrome (the panel's local test, a resume after a bot check). Every
observation returns a `PageState` (url, title, html, visible text, numbered
candidates). Links are acted on by navigation (same approved hosts only,
decided by the caller), buttons by clicking the numbered element.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, replace
from pathlib import Path
from types import TracebackType

from playwright.sync_api import BrowserContext, Page, Playwright

from argus_collector.browser import page_tools as tools
from argus_collector.browser.binding import (
    BINDING_JS,
    PersonBinding,
    PersonProbe,
    parse_result,
    probe_payload,
)
from argus_collector.browser.host import BrowserHost, open_context
from argus_collector.browser.scripts import HIDDEN_LINKS_JS, PLAIN_TEXT_JS
from argus_collector.discovery.contract import Candidate
from argus_collector.runtime import contract as runtime

NAVIGATION_TIMEOUT_MS = 45_000
LOAD_TIMEOUT_MS = 10_000
CLICK_TIMEOUT_MS = 3_000  # WINLOG 06.10.2026: a missing or covered element costs 3 s, not 10
SETTLE_MS = 800  # longest wait for a quiet DOM after load / click
QUIET_MS = 300  # no DOM mutation for this long: the page is ready
CHALLENGE_WAIT_S = 20.0  # target state timeout (TZ_SELAIN 8.5)
CHALLENGE_POLL_MS = 1000


@dataclass(frozen=True)
class PageState:
    url: str
    title: str
    html: str
    text: str
    candidates: list[Candidate]
    challenge: bool = False  # a bot check that did not clear within 20 s
    hidden_hrefs: tuple[str, ...] = ()  # mailto:/tel: links not rendered now
    consent: str = ""  # the cookie banner answered on this page (`necessary: <text>`)
    tab_panels: tuple[tuple[str, str], ...] = ()  # (selected tab label, its panel's text)
    challenge_hint: bool = False  # one bot-check sign only: the vision model may look


class WalkBrowser:
    """Context manager: `with WalkBrowser(headless, profile_dir) as wb: wb.goto(url)`."""

    def __init__(self, headless: bool, profile_dir: Path | None = None,
                 host: BrowserHost | None = None, profile: bool = False) -> None:
        self.headless = headless
        self.profile_dir = profile_dir or runtime.browser_profile_dir()
        self.host, self.profile = host, profile  # profile: the work-browser profile
        self.start_ms = 0  # Chrome start for this walk (0: the collection's Chrome ran)
        self._pw: Playwright | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._consented: set[str] = set()

    def __enter__(self) -> WalkBrowser:
        self._pw, self._context, self.start_ms = open_context(
            self.host, self.profile, self.headless, self.profile_dir)
        self._page = self._context.pages[0] if self._context.pages else self._context.new_page()
        self._page.set_default_navigation_timeout(NAVIGATION_TIMEOUT_MS)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        for close in (
            self._context.close if self._context else None,
            self._pw.stop if self._pw else None,
        ):
            if close is None:
                continue
            try:
                close()
            except Exception:  # noqa: BLE001 - closing must never hide the walk result
                pass
        self._context, self._pw, self._page = None, None, None

    @property
    def page(self) -> Page:
        if self._page is None:
            raise RuntimeError("WalkBrowser is not open")
        return self._page

    def _settle(self) -> None:
        """`load`, then a quiet DOM (300 ms without a mutation, 800 ms at most)."""
        tools.settle(self.page, LOAD_TIMEOUT_MS, QUIET_MS, SETTLE_MS)

    def _challenged(self) -> bool:
        found = tools.challenged(self.page)
        if found is None:  # the check reloads the page right now
            self._settle()
            return True
        return found

    def _ready(self) -> PageState:
        """Observe; a bot check is waited out for up to 20 s (it clears by itself),
        a cookie banner is answered (necessary cookies preferred)."""
        deadline = time.monotonic() + CHALLENGE_WAIT_S
        challenged = waited = self._challenged()
        while challenged and time.monotonic() < deadline:
            self.page.wait_for_timeout(CHALLENGE_POLL_MS)
            challenged = self._challenged()
        consent = ""
        if not challenged:
            if waited:  # the check cleared: the real page has just loaded
                self._settle()
            consent = tools.answer_consent(self.page, self._consented)
            if consent:
                self._settle()
        state = self.observe()
        hint = not challenged and tools.challenge_hint(self.page)
        return replace(state, challenge=challenged, consent=consent, challenge_hint=hint)

    def wait_out_challenge(self) -> PageState:
        """The vision model saw a bot check: wait up to 20 s for it to clear, observe."""
        deadline = time.monotonic() + CHALLENGE_WAIT_S
        while tools.challenge_hint(self.page) and time.monotonic() < deadline:
            self.page.wait_for_timeout(CHALLENGE_POLL_MS)
        state = self._ready()
        return replace(state, challenge=state.challenge or state.challenge_hint)

    def screenshot(self) -> bytes:
        """The visible part of the page as JPEG (for the vision model)."""
        return self.page.screenshot(type="jpeg", quality=70)

    def goto(self, url: str) -> PageState:
        """Navigate, wait for DOM content + a short settle, observe."""
        self.page.goto(url, wait_until="domcontentloaded")
        self._settle()
        return self._ready()

    def click(self, candidate: Candidate) -> PageState:
        """Click the numbered element on the current page, wait, observe."""
        self.page.locator(candidate.selector).first.click(timeout=CLICK_TIMEOUT_MS)
        self._settle()
        return self._ready()

    def select(self, candidate: Candidate, option: str) -> PageState:
        """Choose the option labelled `option` in the numbered dropdown, wait, observe."""
        self.page.locator(candidate.selector).first.select_option(
            label=option, timeout=CLICK_TIMEOUT_MS
        )
        self._settle()
        return self._ready()

    def scroll(self) -> PageState:
        """Scroll the window to the bottom, wait, observe."""
        self.page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
        self.page.wait_for_timeout(SETTLE_MS)
        return self.observe()

    def back(self) -> PageState:
        """History back (after an action left the approved hosts), wait, observe."""
        self.page.go_back(wait_until="domcontentloaded")
        self._settle()
        return self._ready()

    def bindings(self, persons: list[PersonProbe]) -> list[PersonBinding]:
        """Structural binding of each probed value to its person, and its group heading."""
        if not persons:
            return []
        return parse_result(self.page.evaluate(BINDING_JS, probe_payload(persons)), persons)

    def observe(self) -> PageState:
        """Current page without acting: html, visible text, candidates."""
        candidates = tools.candidates(self.page)
        read = self.page.evaluate(PLAIN_TEXT_JS) or {}
        text, panels = read.get("text", ""), read.get("panels") or []
        hidden = self.page.evaluate(HIDDEN_LINKS_JS)
        return PageState(
            url=self.page.url,
            title=self.page.title(),
            html=self.page.content(),
            text=str(text),
            candidates=candidates,
            hidden_hrefs=tuple(str(h) for h in hidden),
            tab_panels=tuple((str(p.get("label", "")), str(p.get("text", ""))) for p in panels
                             if isinstance(p, dict)),
        )
