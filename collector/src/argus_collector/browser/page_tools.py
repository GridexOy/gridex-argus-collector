"""Page-level helpers of a walk session (Playwright `Page` in, plain data out).

Candidates of the current page, the bot-check test, and the answer to a
cookie banner: necessary cookies first, then reject, accept only when there
is nothing else (TZ_SELAIN 8.5); the choice is written to the journal.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page

from argus_collector.browser.scripts import (
    CANDIDATES_JS,
    CHALLENGE_JS,
    CONSENT_JS,
    IDX_ATTR,
    PROBE_JS,
    QUIET_DOM_JS,
)
from argus_collector.browser.service import consent_choice, is_challenge, is_challenge_hint
from argus_collector.discovery.contract import Candidate, host_of
from argus_collector.runtime import contract as runtime

CLICK_TIMEOUT_MS = 3_000  # WINLOG 06.10.2026: a missing or covered element costs 3 s, not 10


def candidates(page: Page) -> list[Candidate]:
    return [
        Candidate(
            index=int(item["index"]), kind=str(item["kind"]), text=str(item["text"]),
            href=str(item["href"]), selector=f'[{IDX_ATTR}="{int(item["index"])}"]',
            role=str(item.get("role", "")), state=str(item.get("state", "")),
            options=tuple(str(o) for o in item.get("options", [])),
        )
        for item in page.evaluate(CANDIDATES_JS)
    ]


def settle(page: Page, load_timeout_ms: int, quiet_ms: int, max_ms: int) -> None:
    """`load`, then a quiet DOM: `quiet_ms` without a mutation, `max_ms` at most."""
    try:
        page.wait_for_load_state("load", timeout=load_timeout_ms)
    except PlaywrightError:  # readiness is by content, not by `load`
        pass
    try:
        page.evaluate(QUIET_DOM_JS, [quiet_ms, max_ms])
    except PlaywrightError:  # a navigation during the wait: settled enough
        page.wait_for_timeout(quiet_ms)


def challenged(page: Page) -> bool | None:
    """True / False, None while the page navigates (a check that reloads itself)."""
    try:
        return is_challenge(page.evaluate(CHALLENGE_JS))
    except PlaywrightError:
        return None


def challenge_hint(page: Page) -> bool:
    """One bot-check sign only (an uncertain case for the vision model)."""
    try:
        return is_challenge_hint(page.evaluate(CHALLENGE_JS))
    except PlaywrightError:
        return False


def answer_consent(page: Page, done: set[str]) -> str:
    """Answer a cookie banner once per host; the choice (`necessary: <text>`) or ""."""
    host = host_of(page.url)
    if host in done:
        return ""
    try:
        choice = consent_choice(page.evaluate(CONSENT_JS))
    except PlaywrightError:
        return ""
    if choice is None:
        return ""
    index, kind, text = choice
    done.add(host)
    try:
        page.locator(f'[data-argus-consent="{index}"]').first.click(timeout=CLICK_TIMEOUT_MS)
    except PlaywrightError as exc:
        runtime.journal("browser", f"cookie banner on {host}: {kind} click failed: {exc}"[:200])
        return ""
    runtime.journal("browser", f"cookie banner on {host}: {kind} ({text[:40]})")
    return f"{kind}: {text}"


PROBE_TIMEOUT_MS = 10_000


def probe(page: Page, url: str) -> tuple[int, str]:
    """(HTTP status, final URL after redirects) of `url` with the page's cookies and
    headers, without leaving the page; (0, "") when nothing answers. The page's own
    `fetch` for its origin, the context's request API for another one."""
    try:
        if urlsplit(page.url).netloc == urlsplit(url).netloc:
            status, final = page.evaluate(PROBE_JS, [url, PROBE_TIMEOUT_MS])
            return int(status), str(final)
        resp = page.request.get(url, timeout=PROBE_TIMEOUT_MS, max_redirects=10)
    except PlaywrightError:
        return 0, ""
    return resp.status, resp.url
