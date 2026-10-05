"""Ellego fixture: >9000 characters of mega menu before the first card, 40 people, filters."""

from __future__ import annotations

import html as markup
import re
from collections import Counter
from collections.abc import Iterator
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from test_site.tests.blocks import Block, blocks, e164, page_text
from test_site.tests.client import gold, page, running

HOST = "ellego.localhost"
GOLD = gold("ellego")
CONTACT = GOLD["filters"]["page"]
LABELS: list[str] = GOLD["filters"]["labels"]
PERSONS: list[dict[str, Any]] = GOLD["persons"]
MENU_CHARS = GOLD["menu"]["min_chars_before_first_card"]
OWNER_NAMES = [
    "Mika Mäenpää", "Konstantin Enckell", "Janne Niemi", "Otto Vainio", "Susanna Huovila",
]  # fmt: skip
NAV = [
    ("/", "Home"), ("/products/", "Products"), ("/services/", "Services"),
    ("/references/", "References"), ("/company/", "Company"), ("/contact/", "Contact"),
]  # fmt: skip
FOOTER_LINKS = ('puh. <a href="tel:+358100001000">010 000 1000</a>, '
                '<a href="mailto:info@ellego.example">info@ellego.example</a></p>')  # fmt: skip
GROUP_RE = re.compile(
    r'<div class="team-group" id="([^"]+)" data-group="([^"]+)">\s*<h2>(.*?)</h2>'
)
STYLE = Path(__file__).resolve().parents[1] / "sites" / "ellego" / "style.css"


@pytest.fixture(scope="module")
def site() -> Iterator[ThreadingHTTPServer]:
    with running() as srv:
        yield srv


def fetch(srv: ThreadingHTTPServer, path: str) -> str:
    return page(srv, HOST, "/" + path.lstrip("/"))


def part(html: str, start: str, end: str) -> str:
    """Markup from the first `start` up to the next `end` after it."""
    begin = html.index(start)
    return html[begin : html.index(end, begin)]


def cards(html: str) -> list[tuple[str, Block]]:
    """(h2 heading of the team group around the card, the card) in page order."""
    headings = {gid: markup.unescape(text) for gid, _, text in GROUP_RE.findall(html)}
    found: list[tuple[str, Block]] = []
    for card in (b for b in blocks(html) if "person" in b.classes):
        around = [headings[p] for p in card.parents if p in headings]
        assert len(around) == 1, card.text
        found.append((around[0], card))
    return found


def ascii_email(name: str) -> str:
    plain = name.lower().replace("ä", "a").replace("ö", "o")
    return plain.replace(" ", ".") + "@ellego.example"


def test_every_page_shares_the_header_mega_menu_and_footer(site: ThreadingHTTPServer) -> None:
    pages = {path: fetch(site, path) for path in GOLD["pages"]}
    head, foot = part(pages["/"], "<header", "</header>"), part(pages["/"], "<footer", "</footer>")
    for path, html in pages.items():
        assert '<html lang="en">' in html, path
        assert part(html, "<header", "</header>") == head, path
        assert part(html, "<footer", "</footer>") == foot, path
    nav = part(head, '<nav class="primary-menu"', "</nav>")
    assert re.findall(r'<a href="([^"]+)">([^<]+)</a>', nav) == NAV
    assert [label for _, label in NAV] == GOLD["menu"]["nav"] and GOLD["seed"] == "/"
    company = GOLD["company"]
    assert page_text(foot) == company["footer"] and FOOTER_LINKS in foot
    assert company["footer"].startswith(", ".join((company["name"], *company["address_lines"])))
    phone, email = company["organization_channels"]
    assert e164(phone["text"], "FI") == phone["value"] == "+358100001000"
    assert (email["value"], phone["page"], email["page"]) == ("info@ellego.example", "/", "/")
    names = [p["name"] for p in PERSONS]
    for path, html in pages.items():
        main = part(html, "<main>", "</main>")
        assert (path == CONTACT) == any(name in html for name in names), path
        if path != CONTACT:
            assert "tel:" not in main and "mailto:" not in main and "<button" not in html


def test_mega_menu_text_comes_before_the_first_card(site: ThreadingHTTPServer) -> None:
    html = fetch(site, CONTACT)
    text = page_text(html)
    first = GOLD["menu"]["first_card"]
    before = text[: text.index(first)]
    assert first == PERSONS[0]["name"] and MENU_CHARS == 9000
    assert len(before) > MENU_CHARS, len(before)
    assert not any(p["name"] in before or p["phone_text"] in before for p in PERSONS)
    menu = part(html, '<nav class="mega-menu is-open"', "</nav>")
    assert len(page_text(menu)) > MENU_CHARS and "hidden" not in menu
    assert html.index("</nav>", html.index('class="mega-menu')) < html.index("<main>")
    words = ("Generator sets", "Aggregaatit", "Kompressorit", "Services / Palvelut", "References")
    assert all(word in menu for word in words)
    assert "display: none" not in STYLE.read_text(encoding="utf-8")


def test_forty_cards_equal_the_gold(site: ThreadingHTTPServer) -> None:
    html = fetch(site, CONTACT)
    found, text = cards(html), page_text(html)
    assert len(found) == len(PERSONS) == 40
    for (heading, card), person in zip(found, PERSONS, strict=True):
        shown = [person["name"], person["title"], person["phone_text"]]
        shown += [person["email"]] if person["email"] else []
        assert card.text == " ".join(shown) and heading == person["department"], person["name"]
        assert "\n".join(shown) in text  # name, title, phone and email each on their own line
        assert f'<h3>{person["name"]}</h3><p class="title">{person["title"]}</p>' in html
        assert f'<a href="tel:{person["phone"]}">{person["phone_text"]}</a>' in html
        assert e164(person["phone_text"], "FI") == person["phone"]
        assert re.fullmatch(r"\+358 40 7\d\d \d{4}", person["phone_text"]), person["phone_text"]
        where = (person["country"], person["source_page"], person["jsonld"])
        assert where == ("FI", CONTACT, False), person["name"]
    assert len({p["phone"] for p in PERSONS}) == 40


def test_every_second_card_has_an_ascii_email(site: ThreadingHTTPServer) -> None:
    html = fetch(site, CONTACT)
    for index, person in enumerate(PERSONS):
        if index % 2:
            assert person["email"] is None, person["name"]
            continue
        assert person["email"] == ascii_email(person["name"]) and person["email"].isascii()
        assert f'<a href="mailto:{person["email"]}">{person["email"]}</a>' in html
    assert html.count("mailto:") == 21  # 20 people and the footer


def test_filter_bar_is_plain_buttons_above_all_open_groups(site: ThreadingHTTPServer) -> None:
    html = fetch(site, CONTACT)
    found = blocks(html)
    buttons = [b for b in found if b.tag == "button"]
    assert [b.text for b in buttons] == LABELS and LABELS[0] == GOLD["filters"]["active_on_load"]
    for button in buttons:
        assert button.attrs["type"] == "button" and "role" not in button.attrs, button.text
        assert not any(name.startswith("aria-") for name in button.attrs), button.text
    assert ["is-active" in b.classes for b in buttons] == [True] + [False] * 6
    groups = GROUP_RE.findall(html)
    assert [markup.unescape(text) for _, _, text in groups] == LABELS[1:]
    assert [key for _, key, _ in groups] == [b.attrs["data-filter"] for b in buttons[1:]]
    assert buttons[0].attrs["data-filter"] == "all"
    team = [b for b in found if "team-group" in b.classes]
    assert len(team) == 6 and not any("hidden" in b.attrs for b in team)
    assert html.index('class="filter-bar"') < html.index('class="person"')
    assert not any(word in html for word in ('role="tab', "aria-selected", "aria-expanded"))
    assert "group.hidden = wanted !== 'all' && group.getAttribute('data-group') !== wanted;" in html


def test_owner_named_people_come_first_under_sales_and_marketing(
    site: ThreadingHTTPServer,
) -> None:
    found = cards(fetch(site, CONTACT))
    for (heading, card), name in zip(found, OWNER_NAMES, strict=False):
        assert heading == "Sales & Marketing" and card.text.startswith(name + " "), name
    assert [p["name"] for p in PERSONS if p["priority"]] == OWNER_NAMES
    assert [p["name"] for p in PERSONS[:5]] == OWNER_NAMES
    counts = Counter(p["department"] for p in PERSONS)
    assert counts == {g["heading"]: g["count"] for g in GOLD["groups"]}
    assert list(counts) == LABELS[1:] == [g["heading"] for g in GOLD["groups"]]
    assert [heading for heading, _ in found[:8]] == ["Sales & Marketing"] * 8
