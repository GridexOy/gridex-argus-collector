"""Playwright page session of a walk (the second file that imports Playwright).

`WalkBrowser` keeps one persistent-profile context and one tab. Every
observation returns a `PageState` (url, title, html, visible text, numbered
candidates). Links are acted on by navigation (same approved hosts only,
decided by the caller), buttons by clicking the numbered element.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType

from playwright.sync_api import BrowserContext, Page, Playwright, sync_playwright
from playwright.sync_api import Error as PlaywrightError

from argus_collector.browser.binding import (
    BINDING_JS,
    PersonBinding,
    PersonProbe,
    parse_result,
    probe_payload,
)
from argus_collector.browser.scripts import (
    CANDIDATES_JS,
    CHALLENGE_JS,
    HIDDEN_LINKS_JS,
    IDX_ATTR,
)
from argus_collector.browser.service import is_challenge, launch_kwargs
from argus_collector.discovery.contract import Candidate
from argus_collector.runtime import contract as runtime

NAVIGATION_TIMEOUT_MS = 45_000
LOAD_TIMEOUT_MS = 10_000
CLICK_TIMEOUT_MS = 10_000
SETTLE_MS = 800
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


class WalkBrowser:
    """Context manager: `with WalkBrowser(headless, profile_dir) as wb: wb.goto(url)`."""

    def __init__(self, headless: bool, profile_dir: Path | None = None) -> None:
        self.headless = headless
        self.profile_dir = profile_dir or runtime.browser_profile_dir()
        self._pw: Playwright | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    def __enter__(self) -> WalkBrowser:
        from argus_collector.browser import contract  # noqa: PLC0415 - avoid import cycle

        plan = contract.plan_for_this_machine(headless=self.headless, profile_dir=self.profile_dir)
        plan.user_data_dir.mkdir(parents=True, exist_ok=True)
        self._pw = sync_playwright().start()
        self._context = self._pw.chromium.launch_persistent_context(**launch_kwargs(plan))  # type: ignore[arg-type]
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
        try:
            self.page.wait_for_load_state("load", timeout=LOAD_TIMEOUT_MS)
        except Exception:  # noqa: BLE001 - readiness is by content, not by `load`
            pass
        self.page.wait_for_timeout(SETTLE_MS)

    def _challenged(self) -> bool:
        try:
            return is_challenge(self.page.evaluate(CHALLENGE_JS))
        except PlaywrightError:  # the check reloads the page right now
            self._settle()
            return True

    def _ready(self) -> PageState:
        """Observe; a bot check is waited out for up to 20 s (it clears by itself)."""
        deadline = time.monotonic() + CHALLENGE_WAIT_S
        challenged = self._challenged()
        while challenged and time.monotonic() < deadline:
            self.page.wait_for_timeout(CHALLENGE_POLL_MS)
            challenged = self._challenged()
        if not challenged:
            self._settle()
        state = self.observe()
        return PageState(state.url, state.title, state.html, state.text, state.candidates,
                         challenge=challenged, hidden_hrefs=state.hidden_hrefs)

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
        raw = self.page.evaluate(CANDIDATES_JS)
        candidates = [
            Candidate(
                index=int(item["index"]),
                kind=str(item["kind"]),
                text=str(item["text"]),
                href=str(item["href"]),
                selector=f'[{IDX_ATTR}="{int(item["index"])}"]',
                role=str(item.get("role", "")),
                state=str(item.get("state", "")),
                options=tuple(str(o) for o in item.get("options", [])),
            )
            for item in raw
        ]
        text = self.page.evaluate("() => document.body ? document.body.innerText : ''")
        hidden = self.page.evaluate(HIDDEN_LINKS_JS)
        return PageState(
            url=self.page.url,
            title=self.page.title(),
            html=self.page.content(),
            text=str(text),
            candidates=candidates,
            hidden_hrefs=tuple(str(h) for h in hidden),
        )
