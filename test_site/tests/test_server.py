"""The fixture site serves its pages and every gold record is present in them."""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Iterator
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from test_site import server

GOLD = Path(__file__).resolve().parents[1] / "gold" / "fixture_oy.json"
# The fixture site is local: bypass any system proxy (Windows registry proxy
# otherwise answers 127.0.0.1 with 502 Bad Gateway).
DIRECT_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


@pytest.fixture
def site() -> Iterator[ThreadingHTTPServer]:
    srv = server.start(port=0)
    try:
        yield srv
    finally:
        srv.shutdown()
        srv.server_close()


def fetch(srv: ThreadingHTTPServer, page: str) -> str:
    with DIRECT_OPENER.open(server.base_url(srv) + page, timeout=5) as resp:
        assert resp.status == 200
        return resp.read().decode("utf-8")


def test_home_and_contact_pages_served(site: ThreadingHTTPServer) -> None:
    assert "Fixture Oy" in fetch(site, "")
    assert "<h1>Contact</h1>" in fetch(site, "contact.html")


def test_missing_page_is_404(site: ThreadingHTTPServer) -> None:
    with pytest.raises(urllib.error.HTTPError) as err:
        fetch(site, "nope.html")
    assert err.value.code == 404


def test_gold_records_present_in_pages(site: ThreadingHTTPServer) -> None:
    gold = json.loads(GOLD.read_text(encoding="utf-8"))
    pages = {name: fetch(site, name) for name in ("index.html", "contact.html")}
    company = gold["company"]
    for page in company["source_pages"]:
        assert company["email"] in pages[page]
        assert f"tel:{company['phone']}" in pages[page]
        assert company["business_id"] in pages[page]
    for person in gold["persons"]:
        html = pages[person["source_page"]]
        assert person["name"] in html
        assert person["title"] in html
        assert person["email"] in html
        assert f"tel:{person['phone']}" in html
