"""Reimax fixture: the contact page states the address pattern; 14 cards without email."""

from __future__ import annotations

from collections.abc import Iterator
from http.server import ThreadingHTTPServer
from typing import Any

import pytest

from test_site.tests.blocks import blocks, e164, page_text
from test_site.tests.client import gold, page, running

HOST = "reimax.localhost"
GOLD = gold("reimax")
PATTERN: dict[str, str] = GOLD["pattern"]
PERSONS: list[dict[str, Any]] = GOLD["persons"]


@pytest.fixture(scope="module")
def site() -> Iterator[ThreadingHTTPServer]:
    with running() as srv:
        yield srv


def test_contact_states_the_pattern_above_fourteen_cards(site: ThreadingHTTPServer) -> None:
    html = page(site, HOST, "/" + PATTERN["page"])
    text = page_text(html)
    assert PATTERN["quote"] in text
    assert text.index(PATTERN["quote"]) < text.index(PERSONS[0]["name"]), "the note comes first"
    cards = [b for b in blocks(html) if "person" in b.classes]
    assert len(cards) == len(PERSONS) == 14
    for card, person in zip(cards, PERSONS, strict=True):
        assert person["name"] in card.text and person["title"] in card.text
        assert person["phone_text"] in card.text
        assert e164(person["phone_text"], "FI") == person["phone"]
        assert "@" not in card.text, "no card prints an address"


def test_gold_addresses_follow_the_stated_pattern() -> None:
    assert PATTERN["value"] == "firstname.lastname@reimax.example"
    for person in PERSONS:
        first, last = person["email"].split("@", 1)[0].split(".")
        assert person["email"].endswith("@reimax.example") and first and last
        assert person["email_status"] == "inferred", "never published: oletettu"
    assert sum(p["sales"] for p in PERSONS) == 7, "sales people reach the walk's goal"


def test_only_the_company_channels_are_printed(site: ThreadingHTTPServer) -> None:
    text = page_text(page(site, HOST, "/" + PATTERN["page"]))
    addresses = {w.strip(".,") for w in text.split() if "@" in w}
    assert addresses == {PATTERN["value"], GOLD["company"]["email"]}
    for path in ("/", "/products/", "/about/"):
        other = page_text(page(site, HOST, path))
        assert not any(p["name"] in other for p in PERSONS), path
