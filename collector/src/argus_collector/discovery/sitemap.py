"""The site's own map of itself: `sitemap.xml` (TZ_SELAIN v4.0 4.2 p. 2).

A menu does not always carry the contact page - it can sit behind a mega-menu the
rules do not open, behind a script, or simply be unlinked. `sitemap.xml` lists it
anyway, so the ladder reads the map once per company and keeps the URLs whose words
are contact words. The map is fetched with plain HTTP (no browser page, no page
budget) through whatever proxy the machine uses for the site itself; a map that does
not answer, is not XML or is huge is simply absent - never an error of the walk.
"""

from __future__ import annotations

import re
import urllib.error
import urllib.request
from urllib.parse import urlsplit, urlunsplit

MAP_NAMES = ("/sitemap.xml", "/sitemap_index.xml")
TIMEOUT_S = 10.0
MAX_BYTES = 5_000_000
MAX_URLS = 400
MAX_MAPS = 3  # an index of indexes is read one level deep
LOC = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>", re.I)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ArgusSelain/0.5"


def map_urls(seed: str) -> list[str]:
    """The map URLs to try for a seed, in order."""
    parts = urlsplit(seed)
    if not parts.scheme or not parts.netloc:
        return []
    return [urlunsplit((parts.scheme, parts.netloc, name, "", "")) for name in MAP_NAMES]


def _fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": UA})  # noqa: S310 - http(s) only
    with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:  # noqa: S310
        body: bytes = response.read(MAX_BYTES)
    return body.decode("utf-8", "replace")


def _locations(body: str) -> list[str]:
    return [loc for loc in LOC.findall(body) if loc.startswith(("http://", "https://"))]


def read(seed: str) -> list[str]:
    """Every URL the site's map lists, following one level of a sitemap index.
    An empty list when the site has no readable map - that is not a failure."""
    found: list[str] = []
    maps = map_urls(seed)
    seen_maps: set[str] = set()
    while maps and len(seen_maps) < MAX_MAPS:
        url = maps.pop(0)
        if url in seen_maps:
            continue
        seen_maps.add(url)
        try:
            body = _fetch(url)
        except (urllib.error.URLError, OSError, ValueError):
            continue
        locations = _locations(body)
        if "<sitemapindex" in body[:2000].lower():
            maps = locations[:MAX_MAPS] + maps
            continue
        found += locations
        if len(found) >= MAX_URLS:
            break
    out, seen = [], set()
    for url in found[:MAX_URLS]:
        if url not in seen:
            seen.add(url)
            out.append(url)
    return out
