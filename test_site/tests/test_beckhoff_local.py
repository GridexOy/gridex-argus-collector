"""Beckhoff fixture, local versions: fi-fi people (also JSON-LD), the excluded German site."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from http.server import ThreadingHTTPServer
from typing import Any

import pytest

from test_site.tests.blocks import Block, blocks, e164
from test_site.tests.client import running
from test_site.tests.test_beckhoff import EXCLUDED, GOLD, OFFICE, PAGES, fetch

GERMAN = EXCLUDED["foreign_site"]["persons"]
JSONLD_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)
H2_RE = re.compile(r"<h2>(.*?)</h2>")


@pytest.fixture(scope="module")
def site() -> Iterator[ThreadingHTTPServer]:
    with running() as srv:
        yield srv


def cards(html: str, names: list[str]) -> dict[str, tuple[str, Block]]:
    """Person name -> (the h2 above the card, or "" without one; the card)."""
    chunks = ["", *H2_RE.split(html)]
    found: dict[str, tuple[str, Block]] = {}
    for heading, chunk in zip(chunks[0::2], chunks[1::2], strict=True):
        for card in (b for b in blocks(chunk) if "person" in b.classes):
            name = next(n for n in names if card.text.startswith(n + " "))
            found[name] = (heading, card)
    return found


def check_card(person: dict[str, Any], card: Block, html: str, country: str) -> None:
    for value in (person["name"], person["title"], person["phone_text"], person["email"]):
        assert value in card.text, (person["name"], value)
    assert f'href="tel:{person["phone"]}">{person["phone_text"]}</a>' in html
    assert f'href="mailto:{person["email"]}"' in html
    assert e164(person["phone_text"], country) == person["phone"]
    assert person["email"].endswith("@beckhoff.example") and person["email"].isascii()


def test_finnish_contacts_page_has_the_office_and_departments(site: ThreadingHTTPServer) -> None:
    path = OFFICE["also_on"]
    html = fetch(site, path)
    office = next(b for b in blocks(html) if "office" in b.classes)
    phone, fax = f"Puh. {OFFICE['phone_text']}", f"Faksi {OFFICE['fax_text']}"
    assert office.text == " ".join((OFFICE["name"], *OFFICE["address_lines"], phone, fax,
                                    f"Sähköposti {OFFICE['email']}"))  # fmt: skip
    assert f'href="tel:{OFFICE["phone"]}"' in html
    listed = [p for p in GOLD["persons"] if p["source_page"] == path]
    found = cards(html, [p["name"] for p in listed])
    assert len(found) == len(listed) == 6
    for person in listed:
        heading, card = found[person["name"]]
        assert heading == person["department"] and not person["jsonld"], person["name"]
        check_card(person, card, html, "FI")
    departments = [p["department"] for p in listed]
    assert [departments.count(d) for d in ("Myynti", "Tekninen tuki", "Hallinto")] == [3, 2, 1]


def test_johto_json_ld_equals_the_visible_cards(site: ThreadingHTTPServer) -> None:
    html = fetch(site, "fi-fi/yritys/johto/")
    match = JSONLD_RE.search(html)
    assert match is not None
    data = json.loads(match.group(1))
    assert (data["@type"], data["name"]) == ("Organization", OFFICE["name"])
    managers = [p for p in GOLD["persons"] if p["jsonld"]]
    assert all(p["source_page"] == "fi-fi/yritys/johto/" for p in managers)
    found = cards(html, [p["name"] for p in managers])
    assert len(data["employee"]) == len(found) == len(managers) == 2
    for item, person in zip(data["employee"], managers, strict=True):
        assert item["@type"] == "Person" and person["department"] is None
        visible = (person["name"], person["title"], person["phone_text"], person["email"])
        assert (item["name"], item["jobTitle"], item["telephone"], item["email"]) == visible
        check_card(person, found[person["name"]][1], html, "FI")
    assert [p["title"] for p in managers] == ["Toimitusjohtaja", "Talousjohtaja"]
    assert '<a href="/fi-fi/yritys/johto/">Johto</a>' in fetch(site, "fi-fi/yritys/")


def test_german_site_people_are_excluded(site: ThreadingHTTPServer) -> None:
    assert '<a href="/de-de/kontakt/">Kontakt</a>' in fetch(site, "de-de/")
    html = fetch(site, "de-de/kontakt/")
    found = cards(html, [p["name"] for p in GERMAN])
    assert len(found) == len(GERMAN) == 3 and EXCLUDED["foreign_site"]["pages"] == PAGES["de-DE"]
    for person in GERMAN:
        heading, card = found[person["name"]]
        assert heading == person["department"] and person["country"] == "DE"
        check_card(person, card, html, "DE")
    finnish = "".join(fetch(site, path) for path in PAGES["fi-FI"])
    assert not any(p["name"] in finnish or p["email"] in finnish for p in GERMAN)
    assert all(p["country"] == "FI" and p["source_page"].startswith("fi-fi/")
               for p in GOLD["persons"])  # fmt: skip


def test_gold_path_steps_are_on_their_pages(site: ThreadingHTTPServer) -> None:
    for step in GOLD["path"]:
        html = fetch(site, step["page"])
        if step["action"] == "link":
            assert f'<a href="{step["href"]}">{step["label"]}</a>' in html, step
        else:
            role = 'role="tab"' if step["action"] == "tab" else 'class="acc"'
            assert re.search(f'<button [^>]*{role}[^>]*>{step["label"]}</button>', html), step
    assert set(GOLD["priority_pages"]) <= {p for paths in PAGES.values() for p in paths}
