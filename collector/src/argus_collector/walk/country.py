"""The exhibition country's version of the site first (owner 06.10.2026: Carlo Gavazzi
went to /en-br/; Wera and OMICRON to /ru/ - the Chrome language, fixed in `browser`).

When the first page of a job walk is another country's version, or a global one
that names the country's version, the walk goes there before reading anything:
hreflang, a country / language switcher, and from a foreign version also `/fi/`
`/en-fi/` `/fi-fi/` and a page named Finland / Suomi / Nordic
(`discovery.version_candidates`). A candidate is asked
first (status and redirects, without leaving the page): one that leads back to the
version the walk came from (a redirect by IP) or to another country is skipped. A
foreign version without the country's one gives way to the global version. The
panel shows the outcome: `Maa: FI (vaihdettu en-br → en-fi)`.
"""

from __future__ import annotations

from argus_collector.browser import contract as browser
from argus_collector.discovery import contract as discovery
from argus_collector.extraction import contract as extraction
from argus_collector.walk import service
from argus_collector.walk.actions import goto
from argus_collector.walk.state import WalkState

LOCAL, GLOBAL, NONE = "local", "global", "none"


def settle(state: WalkState, wb: browser.WalkBrowser, page: browser.PageState
           ) -> browser.PageState:
    """The first page of a job walk, or the country's version of it."""
    focus = state.focus
    if focus is None or not state.job_mode or state.settings.resume is not None:
        return page
    country = focus.country
    now = discovery.page_country(page.url, extraction.html_language(page.html))
    if now == country:
        return page
    links = [c for c in page.candidates if c.kind == "link"]
    local, world = discovery.version_candidates(page.url, page.html, links, country,
                                                list(focus.languages), now is not None)
    found, kind = _first(state, wb, page.url, local, country), LOCAL
    if found is None and now is not None:  # a foreign version: the global one instead
        found, kind = _first(state, wb, page.url, [(u, False) for u in world], None), GLOBAL
    if found is None and now is None:
        return page  # a global site without the country's version: nothing to say
    was = discovery.version_label(page.url)
    shown = (found or page).url
    detail = f"{country}|{was}|{discovery.version_label(shown) if found else ''}"
    state.step(service.STEP_COUNTRY, f"{detail}|{kind if found else NONE}", shown)
    return found or page


def _first(state: WalkState, wb: browser.WalkBrowser, here: str,
           urls: list[tuple[str, bool]], country: str | None) -> browser.PageState | None:
    """The first candidate that answers, stays on an approved host, does not lead back
    here and - when it must - is `country`'s version (None: no country, global)."""
    left = discovery.normalize_url(here)
    for url, strict in urls:
        if discovery.host_of(url) not in state.hosts or discovery.normalize_url(url) == left:
            continue
        status, final = browser.probe(wb, url)
        if not 200 <= status < 300 or discovery.host_of(final) not in state.hosts:
            continue
        if discovery.normalize_url(final) == left:
            continue  # sent back: the site picks the version by IP (K10 step 2)
        if strict and discovery.url_country(final) != country:
            continue
        try:
            return goto(wb, final)
        except browser.ActionError:
            continue
    return None
