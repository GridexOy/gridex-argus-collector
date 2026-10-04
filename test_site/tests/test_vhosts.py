"""Virtual-host fixtures: routing by Host header, the redirect, gold vs pages."""

from __future__ import annotations

import http.client
import json
from collections.abc import Iterator
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from test_site import companies, server

ROOT = Path(__file__).resolve().parents[1]
GOLD_DIR = ROOT / "gold"


@pytest.fixture(scope="module")
def site() -> Iterator[ThreadingHTTPServer]:
    srv = server.start(port=0)
    try:
        yield srv
    finally:
        srv.shutdown()
        srv.server_close()


def get(srv: ThreadingHTTPServer, host: str, path: str) -> tuple[int, str, str]:
    """GET with an explicit Host header (no DNS needed for *.localhost)."""
    port = srv.server_address[1]
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request("GET", path, headers={"Host": f"{host}:{port}"})
        resp = conn.getresponse()
        body = resp.read().decode("utf-8", errors="replace")
        return resp.status, resp.getheader("Location") or "", body
    finally:
        conn.close()


def gold(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((GOLD_DIR / f"{name}.json").read_text(encoding="utf-8"))
    return data


def test_hosts_are_routed_to_their_own_site(site: ThreadingHTTPServer) -> None:
    assert "Fixture Oy" in get(site, "127.0.0.1", "/")[2]
    assert "Nordtec AB" in get(site, "nordtec.localhost", "/")[2]
    assert "Vogel Antriebstechnik" in get(site, "vogel.localhost", "/")[2]
    assert get(site, "nobody.localhost", "/")[0] == 404


def test_katsa_seed_redirects_off_its_approved_host(site: ThreadingHTTPServer) -> None:
    status, location, _ = get(site, "katsa-oy.localhost", "/")
    port = site.server_address[1]
    assert status == 302
    assert location == f"http://katsa-group.localhost:{port}/"
    body = get(site, "katsa-group.localhost", "/")[2]
    for value in ("010 123 4001", "matti.katsa@katsa-group.example"):
        assert value in body


VHOST_GOLD = [("nordtec", "nordtec.localhost"), ("vogel", "vogel.localhost")]


@pytest.mark.parametrize(("name", "host"), VHOST_GOLD)
def test_gold_persons_are_on_their_pages(site: ThreadingHTTPServer, name: str, host: str) -> None:
    data = gold(name)
    for person in data["persons"]:
        status, _, html = get(site, host, "/" + person["source_page"])
        assert status == 200
        assert person["name"] in html and person["title"] in html
        assert person["email"] in html
        assert person.get("phone_text", "") in html
    for channel in data["company"]["organization_channels"]:
        html = get(site, host, "/" + channel["page"])[2]
        assert channel["value"] in html or f"tel:{channel['value']}" in html
    for page in data["priority_pages"] + data["later_pages"]:
        assert get(site, host, "/" + page)[0] == 200


def test_companies_json_matches_the_default_port() -> None:
    on_disk = json.loads(companies.JSON_FILE.read_text(encoding="utf-8"))
    assert on_disk == companies.companies(companies.DEFAULT_PORT)
    ids = [c["company_id"] for c in on_disk]
    assert ids == ["fixture_oy", "nordtec", "vogel", "katsa"]
    for company in on_disk:
        assert company["priority_countries"] == ["FI"]
