"""Malux fixture: four department tabs, every person in its tab and group, SE sister site."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator
from http.server import ThreadingHTTPServer
from typing import Any

import pytest

from test_site.tests.blocks import Block, blocks, e164
from test_site.tests.client import gold, page, port_of, running

GOLD = gold("malux")
FI = [p for p in GOLD["persons"] if p["country"] == "FI"]
SE = [p for p in GOLD["persons"] if p["country"] == "SE"]
TABS = ["ATEX/Teollisuus", "Hallinto", "Valaistus", "Varasto"]
# (tab, group) -> fewest people the owner's case asks for
MINIMUM = {
    ("ATEX/Teollisuus", "Myynti"): 3, ("ATEX/Teollisuus", "Tekninen tuki"): 2,
    ("Hallinto", "Johto"): 2, ("Hallinto", "Talous"): 2, ("Hallinto", "Henkilöstö"): 1,
    ("Valaistus", "Myynti"): 3, ("Valaistus", "Markkinointi"): 2,
    ("Varasto", "Logistiikka"): 5,
}  # fmt: skip


@pytest.fixture(scope="module")
def site() -> Iterator[ThreadingHTTPServer]:
    with running() as srv:
        yield srv


def fetch(srv: ThreadingHTTPServer, where: str) -> str:
    """`where` is gold style `host/path`."""
    host, _, path = where.partition("/")
    return page(srv, host, "/" + path)


def cards(html: str) -> dict[str, tuple[Block, str | None]]:
    """Person name -> (card, label of the tab whose panel holds it)."""
    found = blocks(html)
    tab_of_panel = {b.attrs["aria-controls"]: b.text for b in found if b.attrs.get("role") == "tab"}
    result: dict[str, tuple[Block, str | None]] = {}
    for card in (b for b in found if "person" in b.classes):
        tab = next((tab_of_panel[p] for p in card.parents if p in tab_of_panel), None)
        names = [p["name"] for p in GOLD["persons"] if card.text.startswith(p["name"] + " ")]
        assert len(names) == 1, f"card of nobody in the gold file: {card.text}"
        result[names[0]] = (card, tab)
    return result


def check_person(person: dict[str, Any], card: Block, tab: str | None, html: str) -> None:
    assert card.heading == person["department"] and tab == person["tab"], person["name"]
    for value in (person["name"], person["title"], person["phone_text"], person["email"]):
        assert value in card.text
    assert f'href="mailto:{person["email"]}"' in html
    assert e164(person["phone_text"], person["country"]) == person["phone"]
    assert person["email"].endswith("@malux.example")


def test_four_tabs_in_order_only_the_first_open(site: ThreadingHTTPServer) -> None:
    found = blocks(fetch(site, GOLD["tabs"]["page"]))
    tabs = [b for b in found if b.attrs.get("role") == "tab"]
    panels = [b for b in found if b.attrs.get("role") == "tabpanel"]
    assert [t.text for t in tabs] == TABS == GOLD["tabs"]["labels"]
    assert [t.attrs["aria-selected"] for t in tabs] == ["true", "false", "false", "false"]
    assert ["hidden" in p.attrs for p in panels] == [False, True, True, True]
    for tab, panel in zip(tabs, panels, strict=True):
        assert panel.attrs["id"] == tab.attrs["aria-controls"]
        assert panel.attrs["aria-labelledby"] == tab.attrs["id"]
        assert 5 <= sum("person" in b.classes for b in found if panel.attrs["id"] in b.parents) <= 7


def test_every_finnish_person_sits_in_its_tab_and_group(site: ThreadingHTTPServer) -> None:
    html = fetch(site, "malux.localhost/fi/yhteystiedot/")
    found = cards(html)
    assert len(found) == len(FI) == 20
    for person in FI:
        assert person["source_page"] == "malux.localhost/fi/yhteystiedot/"
        check_person(person, *found[person["name"]], html)
    counts = Counter((p["tab"], p["department"]) for p in FI)
    assert set(counts) == set(MINIMUM)
    assert all(counts[key] >= least for key, least in MINIMUM.items())
    assert {p["department"] for p in FI} >= set(GOLD["priority_departments"])


def test_joakim_flakholm_is_johto_in_hallinto(site: ThreadingHTTPServer) -> None:
    card, tab = cards(fetch(site, "malux.localhost/fi/yhteystiedot/"))["Joakim Flakholm"]
    assert (tab, card.heading) == ("Hallinto", "Johto") and "Maajohtaja" in card.text
    person = next(p for p in FI if p["name"] == "Joakim Flakholm")
    assert (person["tab"], person["department"]) == ("Hallinto", "Johto")
    assert person["title"] == "Maajohtaja"
    directors = [p for p in FI if (p["tab"], p["department"]) == ("Hallinto", "Johto")]
    assert len(directors) == 2


def test_swedish_people_carry_country_se(site: ThreadingHTTPServer) -> None:
    html = fetch(site, "malux-se.localhost/sv/kontakt/")
    assert '<html lang="sv-SE">' in html and "Växel 08-123 456 00" in html
    found = cards(html)
    assert len(found) == len(SE) == 5
    for person in SE:
        assert person["source_page"] == "malux-se.localhost/sv/kontakt/" and person["tab"] is None
        check_person(person, *found[person["name"]], html)


def test_offices_are_on_their_pages(site: ThreadingHTTPServer) -> None:
    for office in GOLD["company"]["offices"]:
        html = fetch(site, office["page"])
        for value in (office["name"], *office["address_lines"], office["phone_text"]):
            assert value in html
        assert f'href="mailto:{office["email"]}"' in html
        assert e164(office["phone_text"], office["country"]) == office["phone"]


def test_language_links_cross_hosts_on_the_request_port(site: ThreadingHTTPServer) -> None:
    port = port_of(site)
    root = page(site, "malux.localhost", "/")
    assert '<a href="/fi/" hreflang="fi">Suomi</a>' in root
    assert f'<a href="http://malux-se.localhost:{port}/sv/" hreflang="sv">Sverige</a>' in root
    fi_home = fetch(site, GOLD["priority_pages"][0])
    assert '<html lang="fi-FI">' in fi_home and ">Tuotteet</a>" in fi_home
    assert '<a href="/fi/yhteystiedot/">Yhteystiedot</a>' in fi_home
    se_link = f'href="http://malux-se.localhost:{port}/sv/" hreflang="sv"'
    assert f'{se_link} title="Malux Sverige">SE</a>' in fi_home
    sv_home = fetch(site, GOLD["later_pages"][0])
    assert '<a href="/sv/kontakt/">Kontakt</a>' in sv_home
    assert f'href="http://malux.localhost:{port}/fi/"' in sv_home
    for where in GOLD["priority_pages"] + GOLD["later_pages"]:
        assert "__PORT__" not in fetch(site, where)
