"""Playwright page session of a walk (the second file that imports Playwright).

`WalkBrowser` keeps one persistent-profile context and one tab. Every
observation returns a `PageState` (url, title, html, visible text, numbered
candidates). Links are acted on by navigation (same approved hosts only,
decided by the caller), buttons by clicking the numbered element.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import TracebackType

from playwright.sync_api import BrowserContext, Page, Playwright, sync_playwright

from argus_collector.browser.binding import BINDING_JS, PersonProbe, parse_result, probe_payload
from argus_collector.browser.service import launch_kwargs
from argus_collector.discovery.contract import Candidate
from argus_collector.runtime import contract as runtime

NAVIGATION_TIMEOUT_MS = 45_000
LOAD_TIMEOUT_MS = 10_000
CLICK_TIMEOUT_MS = 10_000
SETTLE_MS = 800
MAX_TEXT_LEN = 120
IDX_ATTR = "data-argus-idx"

# Visible, actionable elements; mailto:/tel: links are values, not actions
# (TZ section 8.4), submit buttons are never pressed (no forms in this step).
CANDIDATES_JS = """
() => {
  const out = [];
  const seen = new Set();
  const nodes = document.querySelectorAll(
    'a[href], button, [role="button"], summary, input[type="button"]');
  let idx = 0;
  for (const el of nodes) {
    const style = window.getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    if (style.display === 'none' || style.visibility === 'hidden') continue;
    if (rect.width === 0 && rect.height === 0) continue;
    if (el.disabled || el.type === 'submit') continue;
    const text = (el.innerText || el.value || el.getAttribute('aria-label') || el.title || '')
      .replace(/\\s+/g, ' ').trim().slice(0, __MAX_TEXT_LEN__);
    const href = el.tagName === 'A' ? (el.href || '') : '';
    if (/^(mailto|tel):/i.test(href)) continue;
    const kind = /^https?:/i.test(href) ? 'link' : 'button';
    if (kind === 'button' && !text) continue;
    const key = kind + '|' + text + '|' + href;
    if (seen.has(key)) continue;
    seen.add(key);
    el.setAttribute('__IDX_ATTR__', String(idx));
    out.push({index: idx, kind: kind, text: text, href: href});
    idx += 1;
  }
  return out;
}
""".replace("__MAX_TEXT_LEN__", str(MAX_TEXT_LEN)).replace("__IDX_ATTR__", IDX_ATTR)


@dataclass(frozen=True)
class PageState:
    url: str
    title: str
    html: str
    text: str
    candidates: list[Candidate]


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

    def goto(self, url: str) -> PageState:
        """Navigate, wait for DOM content + a short settle, observe."""
        self.page.goto(url, wait_until="domcontentloaded")
        self._settle()
        return self.observe()

    def click(self, candidate: Candidate) -> PageState:
        """Click the numbered element on the current page, wait, observe."""
        self.page.locator(candidate.selector).first.click(timeout=CLICK_TIMEOUT_MS)
        self._settle()
        return self.observe()

    def scroll(self) -> PageState:
        """Scroll the window to the bottom, wait, observe."""
        self.page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
        self.page.wait_for_timeout(SETTLE_MS)
        return self.observe()

    def back(self) -> PageState:
        """History back (after an action left the approved hosts), wait, observe."""
        self.page.go_back(wait_until="domcontentloaded")
        self._settle()
        return self.observe()

    def bindings(self, persons: list[PersonProbe]) -> list[tuple[str, ...]]:
        """Structural binding of each probed value to its person on the current DOM."""
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
            )
            for item in raw
        ]
        text = self.page.evaluate("() => document.body ? document.body.innerText : ''")
        return PageState(
            url=self.page.url,
            title=self.page.title(),
            html=self.page.content(),
            text=str(text),
            candidates=candidates,
        )
