"""The fixture site serves its pages and every gold record is present in them."""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Iterator
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from test_site import server

GOLD = Path(__file__).resolve().parents[1] / "gold" / "fixture_oy.json"
PAGES = ("index.html", "contact.html", "team.html", "team-2.html")
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
        body: bytes = resp.read()
        return body.decode("utf-8")


def gold() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(GOLD.read_text(encoding="utf-8"))
    return data


def test_home_and_contact_pages_served(site: ThreadingHTTPServer) -> None:
    assert "Fixture Oy" in fetch(site, "")
    assert "<h1>Contact</h1>" in fetch(site, "contact.html")
    assert "Seuraava sivu" in fetch(site, "team.html")


def test_missing_page_is_404(site: ThreadingHTTPServer) -> None:
    with pytest.raises(urllib.error.HTTPError) as err:
        fetch(site, "nope.html")
    assert err.value.code == 404


def test_company_gold_present(site: ThreadingHTTPServer) -> None:
    company = gold()["company"]
    for page in company["source_pages"]:
        html = fetch(site, page)
        assert company["email"] in html
        assert f"tel:{company['phone']}" in html
        assert company["business_id"] in html
    assert '"@type": "Organization"' in fetch(site, company["jsonld_page"])


def person_evidence(person: dict[str, Any], html: str) -> None:
    local = person["email"].split("@", 1)[0]
    if person["how"] == "link":
        assert person["email"] in html and f"tel:{person['phone']}" in html
    elif person["how"] == "button":
        assert f'data-user="{local}"' in html and person["button"] in html
        assert person["email"] not in html, "hidden until the button is pressed"
    else:
        assert person["email_text"] in html and person["phone_text"] in html
        assert person["email"] not in html, "only the obfuscated form is on the page"


def test_person_gold_present_in_their_pages(site: ThreadingHTTPServer) -> None:
    pages = {name: fetch(site, name) for name in PAGES}
    for person in gold()["persons"]:
        html = pages[person["source_page"]]
        assert person["name"] in html and person["title"] in html
        person_evidence(person, html)
