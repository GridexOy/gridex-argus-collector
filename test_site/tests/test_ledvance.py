"""LEDVANCE fixture: country accordion, only Finland's office, people behind the bot check."""

from __future__ import annotations

from collections.abc import Iterator
from http.server import ThreadingHTTPServer
from typing import Any

import pytest

from test_site.tests.blocks import Block, blocks, by_id, e164
from test_site.tests.client import CHALLENGE_TITLE, WAF_PASS, gold, page, running

HOST = "ledvance.localhost"
GOLD = gold("ledvance")
OFFICE: dict[str, Any] = GOLD["company"]["offices"][0]
CONTACT = "/" + OFFICE["page"]
EXCLUDED = {item["kind"]: item for item in GOLD["excluded"]}
COUNTRIES = [
    "Austria", "Belgium", "Denmark", "Finland", "France", "Germany",
    "Italy", "Norway", "Poland", "Sweden", "United Kingdom",
]  # fmt: skip


@pytest.fixture(scope="module")
def site() -> Iterator[ThreadingHTTPServer]:
    with running() as srv:
        yield srv


def accordion(html: str) -> dict[str, Block]:
    """Country name -> its panel; checks the accordion wiring on the way."""
    found = blocks(html)
    panels: dict[str, Block] = {}
    for button in (b for b in found if "acc" in b.classes):
        panel = by_id(found, button.attrs["aria-controls"])
        assert button.attrs["aria-expanded"] == "false" and "hidden" in panel.attrs
        assert panel.attrs["role"] == "region"
        assert panel.attrs["aria-labelledby"] == button.attrs["id"]
        assert panel.heading == button.text
        panels[button.text] = panel
    return panels


def test_home_links_to_contact_without_country_switcher(site: ThreadingHTTPServer) -> None:
    html = page(site, HOST, "/")
    assert '<html lang="en">' in html
    for link in ("/en-int/products/", "/en-int/company/", "/en-int/company/contact/"):
        assert f'href="{link}"' in html
    assert "fi-fi" not in html and "<select" not in html
    products = page(site, HOST, "/en-int/products/")
    assert "mailto:" not in products and "Phone" not in products


def test_accordion_has_eleven_closed_countries_alphabetically(site: ThreadingHTTPServer) -> None:
    panels = accordion(page(site, HOST, CONTACT))
    assert list(panels) == COUNTRIES == sorted(COUNTRIES)
    assert "Contact LEDVANCE worldwide" in page(site, HOST, CONTACT)


def test_finland_office_gold_is_in_the_finland_section(site: ThreadingHTTPServer) -> None:
    html = page(site, HOST, CONTACT)
    finland = accordion(html)[OFFICE["section"]]
    lines = (OFFICE["name"], *OFFICE["address_lines"], OFFICE["email"])
    expected = " ".join((*lines[:3], f"Phone {OFFICE['phone_text']}"))
    assert finland.text.startswith(expected)
    assert all(line in finland.text for line in lines)
    assert e164(OFFICE["phone_text"], "FI") == OFFICE["phone"] == "+358974223300"
    assert f'href="mailto:{OFFICE["email"]}"' in html
    local = OFFICE["local_site"]
    assert f'<a href="{local["href"]}">{local["text"]}</a>' in html
    assert OFFICE["country"] == "FI"


def test_finland_fax_is_on_the_page_but_excluded(site: ThreadingHTTPServer) -> None:
    fax = EXCLUDED["fax"]
    finland = accordion(page(site, HOST, CONTACT))["Finland"]
    assert f"Fax {fax['value_text']}" in finland.text
    assert e164(fax["value_text"], "FI") == fax["value"] == "+358974223301"
    assert fax["value"] != OFFICE["phone"]
    assert fax["value"] not in {person["phone"] for person in GOLD["persons"]}


def test_other_countries_are_present_hidden_and_excluded(site: ThreadingHTTPServer) -> None:
    html = page(site, HOST, CONTACT)
    panels = accordion(html)
    others = EXCLUDED["other_countries"]["offices"]
    assert [o["section"] for o in others] == [c for c in COUNTRIES if c != "Finland"]
    for office in others:
        text = panels[office["section"]].text
        assert text.startswith(office["name"]) and office["email"] in text
        assert f"Phone {office['phone_text']}" in text and f"Fax {office['fax_text']}" in text
        assert e164(office["phone_text"], office["country"]) == office["phone"]
        assert e164(office["fax_text"], office["country"]) == office["fax"]
        assert f'href="{office["local_site"]}"' in html
        assert office["email"].endswith("@ledvance.example")


def test_dropdown_page_shows_the_same_offices(site: ThreadingHTTPServer) -> None:
    panels = accordion(page(site, HOST, CONTACT))
    html = page(site, HOST, "/en-int/company/contact-select/")
    found = blocks(html)
    options = [b for b in found if b.tag == "option"]
    assert (options[0].attrs["value"], options[0].text) == ("", "")
    assert [o.text for o in options[1:]] == COUNTRIES
    assert '<label for="country">Choose your country</label>' in html
    for option in options[1:]:
        office = by_id(found, "o-" + option.attrs["value"])
        assert "hidden" in office.attrs and office.attrs["data-country"] == option.attrs["value"]
        assert office.text == f"{option.text} {panels[option.text].text}"


def test_finnish_people_are_behind_the_bot_check(site: ThreadingHTTPServer) -> None:
    path = "/fi-fi/yhteystiedot/"
    assert CHALLENGE_TITLE in page(site, HOST, path)
    html = page(site, HOST, path, WAF_PASS)
    assert '<html lang="fi-FI">' in html
    assert "Asiakaspalvelu puh. 09-7422 3300" in html and OFFICE["email"] in html
    cards = [b for b in blocks(html) if "person" in b.classes]
    assert len(cards) == len(GOLD["persons"]) == 6
    for person, card in zip(GOLD["persons"], cards, strict=True):
        for value in (person["name"], person["title"], person["phone_text"], person["email"]):
            assert value in card.text
        assert f'href="mailto:{person["email"]}"' in html
        assert e164(person["phone_text"], "FI") == person["phone"]
        assert (person["source_page"], person["country"]) == ("fi-fi/yhteystiedot/", "FI")
    contact = page(site, HOST, CONTACT)
    assert not any(person["name"] in contact for person in GOLD["persons"])


def test_priority_pages_answer_after_the_check(site: ThreadingHTTPServer) -> None:
    home = page(site, HOST, "/fi-fi/", WAF_PASS)
    assert '<a href="/fi-fi/yhteystiedot/">Yhteystiedot</a>' in home
    for nav in ("Tuotteet", "Yritys"):
        assert f">{nav}</a>" in home
    for name in GOLD["priority_pages"]:
        assert CHALLENGE_TITLE not in page(site, HOST, "/" + name, WAF_PASS)
    assert GOLD["bot_check"]["paths"] == ["fi-fi/"]
