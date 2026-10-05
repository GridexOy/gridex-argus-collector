"""Coverage facts a page gives (TZ_SELAIN 8.5, 8.10; ARGUS20_TZ_TANDEM.md A4.3).

1. A directory that states its size (`37 henkilöä`, `Showing 1-10 of 37`,
   `Näytetään 1–10 / 37`) gives the expected count of the catalog; it is
   taken only on a page where people were found and when it is at least the
   number found there.
2. A relevant link (contact, team, the country version) to a host of the
   same brand that is not approved (`ledvance.fi` next to `ledvance.com`)
   is a gap `domain_ownership_unresolved`: the owner may add it as
   `owner_known_url`, the walk does not open it (K7).
"""

from __future__ import annotations

import re

from argus_collector.discovery import contract as discovery
from argus_collector.walk.state import WalkState

TOTAL_WORDS = (
    "henkilöä", "henkilöt", "yhteyshenkilöä", "työntekijää", "hakutulosta", "tulosta",
    "results", "people", "persons", "contacts", "employees", "members", "personer",
    "träffar", "medarbetare", "ergebnisse", "treffer", "mitarbeiter", "kontakte",
)
COUNT_RE = re.compile(r"\b(\d{1,4})\s+(" + "|".join(TOTAL_WORDS) + r")\b", re.IGNORECASE)
RANGE_RE = re.compile(r"\b\d{1,4}\s*[-–]\s*\d{1,4}\s*(?:of|/|av|von|yhteensä)\s*(\d{1,4})\b",
                      re.IGNORECASE)
DOMAIN_GAP = "domain_ownership_unresolved"


def declared_total(text: str) -> int:
    """The largest record count the page text declares, 0 when none."""
    found = [int(m.group(1)) for m in COUNT_RE.finditer(text)]
    found += [int(m.group(1)) for m in RANGE_RE.finditer(text)]
    return max(found, default=0)


def note_total(state: WalkState, text: str, people_on_page: int) -> None:
    total = declared_total(text) if people_on_page else 0
    if total >= people_on_page:
        state.cp.declared_total = max(state.cp.declared_total, total)


def _brand(host: str) -> str:
    labels = [part for part in host.split(".") if part]
    return labels[-2] if len(labels) >= 2 else host


def note_foreign_links(state: WalkState, page_url: str,
                       links: list[discovery.Candidate]) -> None:
    """Own-brand relevant links on hosts outside approved_hosts become gaps once per host."""
    brands = {_brand(h) for h in state.hosts}
    seen = {discovery.host_of(g.url) for g in state.cp.gaps if g.reason == DOMAIN_GAP}
    for cand in links:
        host = discovery.host_of(cand.href)
        if not host or host in state.hosts or host in seen or _brand(host) not in brands:
            continue
        if discovery.is_social_url(cand.href) or not discovery.strong_link(
            cand.text, cand.href, state.focus
        ):
            continue
        seen.add(host)
        detail = f"{host} is not an approved host (linked from {page_url}: {cand.text[:60]})"
        state.add_gap(cand.href, DOMAIN_GAP, detail, False)
