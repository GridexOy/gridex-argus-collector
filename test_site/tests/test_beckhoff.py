"""Beckhoff fixture, global site: Germany tab open on load, Finland behind Beckhoff Worldwide."""

from __future__ import annotations

import re
from collections.abc import Iterator
from http.server import ThreadingHTTPServer
from typing import Any

import pytest

from test_site.tests.blocks import Block, blocks, by_id, e164
from test_site.tests.client import gold, page, running

HOST = "beckhoff.localhost"
GOLD = gold("beckhoff")
OFFICE: dict[str, Any] = GOLD["company"]["offices"][0]
PRESENCE = GOLD["tabs"]["page"]
EXCLUDED = {item["kind"]: item for item in GOLD["excluded"]}
PAGES = {
    "en": ["en-en/", "en-en/products/", "en-en/industries/", "en-en/support/", "en-en/company/",
           "en-en/company/careers/", PRESENCE, "en-en/contact/", "en-en/imprint/",
           "en-en/privacy/"],
    "fi-FI": ["fi-fi/", "fi-fi/tuotteet/", "fi-fi/yritys/", "fi-fi/yritys/johto/",
              "fi-fi/yhteystiedot/"],
    "de-DE": ["de-de/", "de-de/kontakt/"],
}  # fmt: skip
REGIONS = {
    "Europe": ["Austria", "Belgium", "Denmark", "Finland", "France", "Italy", "Netherlands",
               "Norway", "Poland", "Spain", "Sweden", "Switzerland", "United Kingdom"],
    "Americas": ["Brazil", "Canada", "USA"],
    "Asia / Pacific": ["China", "India", "Japan"],
}  # fmt: skip
NAV = ["Products", "Industries", "Support", "Company", "Contact"]
FOOTER = {"Contact": "/en-en/contact/", "Global presence": "/" + PRESENCE,
          "Imprint": "/en-en/imprint/", "Privacy": "/en-en/privacy/"}  # fmt: skip


@pytest.fixture(scope="module")
def site() -> Iterator[ThreadingHTTPServer]:
    with running() as srv:
        yield srv


def fetch(srv: ThreadingHTTPServer, path: str) -> str:
    return page(srv, HOST, "/" + path)


def menus(html: str) -> tuple[str, str]:
    """Header and footer markup of a page."""
    head = html[html.index("<header") : html.index("</header>")]
    return head, html[html.index("<footer") : html.index("</footer>")]


def accordion(found: list[Block]) -> dict[str, Block]:
    """Country -> its section in the Worldwide panel; checks the wiring on the way."""
    sections: dict[str, Block] = {}
    for button in (b for b in found if "acc" in b.classes):
        panel = by_id(found, button.attrs["aria-controls"])
        assert button.attrs["aria-expanded"] == "false" and "hidden" in panel.attrs
        assert panel.attrs["role"] == "region" and "p-worldwide" in panel.parents
        assert panel.attrs["aria-labelledby"] == button.attrs["id"]
        sections[button.text] = panel
    return sections


def test_every_page_answers_in_its_language(site: ThreadingHTTPServer) -> None:
    root = fetch(site, "")
    assert '<a href="/en-en/">Beckhoff Global (English)</a>' in root and "fi-fi" not in root
    for lang, paths in PAGES.items():
        for path in paths:
            assert f'<html lang="{lang}">' in fetch(site, path), path
    assert GOLD["seed"] == "en-en/" and GOLD["forbidden_pages"] == PAGES["de-DE"]


def test_en_pages_share_their_menus_and_hide_the_local_site(site: ThreadingHTTPServer) -> None:
    html = {path: fetch(site, path) for path in PAGES["en"]}
    head, foot = menus(html["en-en/"])
    assert all(menus(text) == (head, foot) for text in html.values())
    assert [m.group(1) for m in re.finditer(r'<a href="/en-en/[^"]+/">([^<]+)</a>', head)] == NAV
    assert '<a href="/de-de/" hreflang="de">Deutsch</a>' in head
    assert all(f'<a href="{href}">{text}</a>' in foot for text, href in FOOTER.items())
    for path, text in html.items():
        assert ("/fi-fi/" in text) == (path == PRESENCE), path
        if path != PRESENCE:
            assert not any(word in text for word in ("mailto:", "tel:", "Phone", "+49")), path
    assert "Find your local contact person in" in html["en-en/contact/"]
    assert "Beckhoff Automation GmbH &amp; Co. KG, Verl, Germany" in html["en-en/imprint/"]
    assert f'<a href="/{PRESENCE}">Global presence</a>' in html["en-en/company/"]


def test_global_presence_opens_on_the_germany_tab(site: ThreadingHTTPServer) -> None:
    found = blocks(fetch(site, PRESENCE))
    tabs = [b for b in found if b.attrs.get("role") == "tab"]
    panels = [b for b in found if b.attrs.get("role") == "tabpanel"]
    assert [t.text for t in tabs] == GOLD["tabs"]["labels"] == ["Germany", "Beckhoff Worldwide"]
    assert [t.attrs["aria-selected"] for t in tabs] == ["true", "false"]
    assert ["hidden" in p.attrs for p in panels] == [False, True]
    assert (GOLD["tabs"]["open"], GOLD["tabs"]["walk"]) == ("Germany", "Beckhoff Worldwide")
    for tab, panel in zip(tabs, panels, strict=True):
        assert panel.attrs["id"] == tab.attrs["aria-controls"]
        assert panel.attrs["aria-labelledby"] == tab.attrs["id"]


def test_germany_panel_is_the_excluded_foreign_tab(site: ThreadingHTTPServer) -> None:
    html = fetch(site, PRESENCE)
    offices = [b for b in blocks(html) if "office" in b.classes and "p-germany" in b.parents]
    expected = EXCLUDED["foreign_tab"]["offices"]
    assert len(offices) == len(expected) == 9 and EXCLUDED["foreign_tab"]["country"] == "DE"
    for block, office in zip(offices, expected, strict=True):
        assert block.heading == office["section"] and block.text.startswith(office["name"])
        lines = (*office["address_lines"], f"Phone {office['phone_text']}", office["email"])
        assert all(line in block.text for line in (office.get("office", ""), *lines))
        assert e164(office["phone_text"], "DE") == office["phone"]
        assert f'href="mailto:{office["email"]}"' in html
    head = expected[0]
    assert f"Fax {head['fax_text']}" in offices[0].text and head["fax"] == "+495246000198"
    assert '<a href="/de-de/">www.beckhoff.com/de-de</a>' in html and head["phone"] == "+4952460000"


def test_worldwide_panel_lists_closed_countries_by_region(site: ThreadingHTTPServer) -> None:
    html = fetch(site, PRESENCE)
    found = blocks(html)
    sections = accordion(found)
    by_region: dict[str, list[str]] = {}
    for country, section in sections.items():
        by_region.setdefault(section.heading, []).append(country)
    assert by_region == REGIONS
    world = by_id(found, "p-worldwide").text
    assert world.startswith("Beckhoff subsidiaries and distributors worldwide. Select a country.")
    for country, section in sections.items():  # label on its own line, its section right after
        tag = '<h4><button type="button" class="acc" aria-expanded="false" aria-controls='
        pattern = f'{tag}"{section.attrs["id"]}" id="[^"]+">{country}</button></h4>\\s*<div id='
        assert re.search(pattern, html), country


def test_finland_section_holds_exactly_the_gold_office(site: ThreadingHTTPServer) -> None:
    html = fetch(site, PRESENCE)
    finland = accordion(blocks(html))[OFFICE["section"]]
    local = OFFICE["local_site"]
    expected = (OFFICE["name"], *OFFICE["address_lines"], f"Puh. {OFFICE['phone_text']}",
                f"Faksi {OFFICE['fax_text']}", f"E-mail {OFFICE['email']}",
                f"Local website {local['text']}")  # fmt: skip
    assert finland.text == " ".join(expected) and finland.heading == OFFICE["region"]
    assert e164(OFFICE["phone_text"], "FI") == OFFICE["phone"] == "+358201233800"
    assert e164(OFFICE["fax_text"], "FI") == OFFICE["fax"] == "+358201233801"
    assert f'<a href="mailto:{OFFICE["email"]}">{OFFICE["email"]}</a>' in html
    assert f'<a href="{local["href"]}">{local["text"]}</a>' in html and local["href"] == "/fi-fi/"
    assert (OFFICE["country"], OFFICE["tab"], OFFICE["page"]) == ("FI", "Beckhoff Worldwide",
                                                                  PRESENCE)  # fmt: skip


def test_other_countries_are_closed_and_excluded(site: ThreadingHTTPServer) -> None:
    html = fetch(site, PRESENCE)
    sections = accordion(blocks(html))
    others = EXCLUDED["closed_country_sections"]["offices"]
    assert [o["section"] for o in others] == [c for c in sections if c != "Finland"]
    for office in others:
        text = sections[office["section"]].text
        assert text.startswith(" ".join((office["name"], *office["address_lines"])))
        assert f"Phone {office['phone_text']}" in text and f"Fax {office['fax_text']}" in text
        assert e164(office["phone_text"], office["country"]) == office["phone"]
        assert e164(office["fax_text"], office["country"]) == office["fax"]
        assert office["email"] in text and f'href="{office["local_site"]}"' in html
        assert office["region"] == sections[office["section"]].heading
