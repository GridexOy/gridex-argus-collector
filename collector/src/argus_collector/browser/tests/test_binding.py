"""DOM binding of person fields: card, table row, proximity, none."""

from __future__ import annotations

from pathlib import Path

import pytest

from argus_collector.browser import contract as browser
from argus_collector.browser.binding import parse_result

HTML = """<html><body>
<ul>
 <li class="person"><b>Anna</b> Virtanen <span>Sales Director</span>
   <a href="mailto:anna.virtanen@x.example">anna.virtanen@x.example</a>
   <a href="tel:+358401234567">Soita</a></li>
 <li class="person">Mikko Korhonen <span>puh. 040 765 4321</span></li>
</ul>
<table><tr><td>Sari Nieminen</td><td>020 123 4561</td></tr>
       <tr><td>Jukka Laine</td><td>040 222 3333</td></tr></table>
<h2>Customer service</h2><ul><li><span>Sari Ojala</span> <span>Customer Service</span></li></ul>
<p>Elina Koski</p><div><p>Shared desk</p></div><p>elina.koski@x.example</p>
<p>Katri Uusi</p><p>Mikko and Katri: katri.uusi@x.example 040 765 4321</p>
</body></html>"""


def probe(name: str, *values: tuple[str, str, str]) -> browser.PersonProbe:
    return browser.PersonProbe(name, tuple(browser.ProbeValue(*v) for v in values))


@pytest.fixture(scope="module")
def bindings(tmp_path_factory: pytest.TempPathFactory) -> list[tuple[str, ...]]:
    profile = tmp_path_factory.mktemp("profile") / "p"
    page = tmp_path_factory.mktemp("site") / "people.html"
    page.write_text(HTML, encoding="utf-8")
    persons = [
        probe("Anna Virtanen", ("Sales Director", "text", "Sales Director"),
              ("anna.virtanen@x.example", "email", "anna.virtanen@x.example"),
              ("Soita", "phone", "+358401234567")),
        probe("Mikko Korhonen", ("040 765 4321", "phone", "+358407654321")),
        probe("Sari Nieminen", ("020 123 4561", "phone", "+358201234561")),
        probe("Elina Koski", ("elina.koski@x.example", "email", "elina.koski@x.example")),
        probe("Katri Uusi", ("katri.uusi@x.example", "email", "katri.uusi@x.example")),
        probe("Nobody Here", ("nobody@x.example", "email", "nobody@x.example")),
        probe("Sari Ojala", ("Customer Service", "text", "Customer Service")),
    ]
    with browser.WalkBrowser(headless=True, profile_dir=profile) as wb:
        wb.goto(Path(page).as_uri())
        return wb.bindings(persons)


def test_card_row_proximity_and_none(bindings: list[tuple[str, ...]]) -> None:
    anna, mikko, sari, elina, katri, nobody, ojala = bindings
    assert ojala == ("card",), "the heading with the same words is not the card"
    assert anna == ("card", "card", "card"), "split name, title, mailto and tel: href"
    assert mikko == ("card",)
    assert sari == ("table_row",)
    assert elina == ("proximity_only",), "only the page body joins them"
    assert katri == ("proximity_only",), "another person's phone is in the same element"
    assert nobody == ("none",)


def test_parse_result_is_defensive() -> None:
    persons = [probe("A", ("x", "text", "x"), ("y", "text", "y"))]
    assert parse_result([["card", "bogus"]], persons) == [("card", "none")]
    assert parse_result(None, persons) == [("none", "none")]
