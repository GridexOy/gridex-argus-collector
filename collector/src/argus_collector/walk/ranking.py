"""Which candidates the rules may act on, in order (links first, then buttons).

Page links plus the frontier links of earlier pages and of the site map, ranked by
the contact words of 4.2; a link that only led back to a walked page is left out, and
so is a button already pressed in this page state.
"""

from __future__ import annotations

from argus_collector.browser import contract as browser
from argus_collector.discovery import contract as discovery
from argus_collector.walk import structure
from argus_collector.walk.state import WalkState

MAX_LINKS_SHOWN = 30
MAX_BUTTONS_SHOWN = 10


def ranked(state: WalkState, page: browser.PageState) -> list[discovery.Candidate]:
    """Page links plus frontier links from earlier pages, then the page's buttons; not
    a link that only led back to a walked page, not a button pressed in this page state."""
    frontier = [c for c in state.frontier_candidates() if not structure.foreign(state, c)]
    pool = structure.offered(state, page.candidates) + frontier
    ordered = discovery.rank_candidates(pool, state.walked(), state.hosts, state.focus)
    links = [c for c in ordered if c.kind == "link"][:MAX_LINKS_SHOWN]
    finished = discovery.normalize_url(page.url) in state.finished_urls  # finish_branch
    pressed = state.clicked.get(state.current_key, set()) | state.failed_targets
    buttons = [c for c in ordered if c.kind == "button" and c.selector not in pressed
               and not finished]
    return links + buttons[:MAX_BUTTONS_SHOWN]
