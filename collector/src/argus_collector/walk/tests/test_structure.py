"""Structure rules before the model: the exhibition country of a country list,
every department tab (sales first), done once per page and label."""

from __future__ import annotations

import sqlite3
from typing import cast

from argus_collector.browser import contract as browser
from argus_collector.discovery import contract as discovery
from argus_collector.models import contract as models
from argus_collector.walk import service, structure
from argus_collector.walk.state import WalkState

URL = "https://www.example.com/en-int/company/contact"


def state() -> WalkState:
    settings = service.WalkSettings(start_url=URL, model=models.ModelConfig("http://x/v1", "m"))
    return WalkState(
        settings, sqlite3.connect(":memory:"), cast(models.ModelClient, None), lambda e: None,
        lambda: False, "run-1", hosts=frozenset({"example.com"}),
        focus=discovery.make_focus(["FI"], ["fi", "en"]),
    )


def page(cands: list[discovery.Candidate]) -> browser.PageState:
    return browser.PageState(URL, "Contact", "<html></html>", "Contact", cands)


def cand(i: int, text: str, role: str = "", state_: str = "", kind: str = "button",
         href: str = "", options: tuple[str, ...] = ()) -> discovery.Candidate:
    return discovery.Candidate(i, kind, text, href, f"#c{i}", role, state_, options)


COUNTRIES = [cand(i, name, "expand", "off") for i, name in enumerate(
    ("Austria", "Denmark", "Finland", "France", "Sweden"))]


def test_only_the_exhibition_country_is_opened_and_offered() -> None:
    walk = state()
    action = structure.structural_action(walk, page(COUNTRIES))
    assert action is not None and action.kind == service.ACTION_CLICK
    assert action.candidate is not None and action.candidate.text == "Finland"
    offered = structure.offered(walk, [*COUNTRIES, cand(9, "Products", kind="link",
                                                        href="https://www.example.com/p")])
    assert [c.text for c in offered] == ["Finland", "Products"]
    assert structure.structural_action(walk, page(COUNTRIES)) is None, "done once"


def test_dropdown_selects_the_exhibition_country() -> None:
    select = cand(0, "Choose your country", kind="select",
                  options=("", "Austria", "Finland", "Germany"))
    action = structure.structural_action(state(), page([select]))
    assert action is not None and action.kind == service.ACTION_SELECT
    assert action.option == "Finland"


def test_every_department_tab_sales_first() -> None:
    walk = state()
    tabs = [cand(0, "ATEX/Teollisuus", "tab", "on"), cand(1, "Hallinto", "tab", "off"),
            cand(2, "Myynti", "tab", "off"), cand(3, "Varasto", "tab", "off")]
    order = []
    for _ in range(5):
        action = structure.structural_action(walk, page(tabs))
        if action is None:
            break
        assert action.candidate is not None
        order.append(action.candidate.text)
    assert order == ["Myynti", "Hallinto", "Varasto"], "the open tab is already read"


def test_collapsed_sections_only_on_a_page_with_contacts() -> None:
    walk = state()
    sections = [cand(0, "Huolto", "expand", "off"), cand(1, "Myynti", "expand", "off")]
    assert structure.structural_action(walk, page(sections)) is None
    walk.page_has_contacts = True
    action = structure.structural_action(walk, page(sections))
    assert action is not None and action.candidate is not None
    assert action.candidate.text == "Myynti"
