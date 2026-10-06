"""Owner 06.10.2026 (Blåkläder: «Löydetty: 44» for 22 people): when collecting, the
Keruu table and its count belong to the company being walked, not to the session."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Iterator
from pathlib import Path

import pytest

from argus_collector.extraction.contract import Contact, VerifiedField
from argus_collector.ui import contract
from argus_collector.ui.app import PanelApp
from argus_collector.ui.tests.conftest import make_tk_root
from argus_collector.ui.tests.test_ui import display  # noqa: F401 - fixture reuse
from argus_collector.walk import contract as walk


def contact(name: str) -> walk.WalkEvent:
    value = VerifiedField(name, name, 0, len(name), "text")
    person = Contact(value, None, None, None)
    return walk.WalkEvent(walk.EVENT_CONTACT, url="http://x.example/", contact=person)


@pytest.fixture
def app(display: str, monkeypatch: pytest.MonkeyPatch,  # noqa: F811 - pytest fixture
        tmp_path: Path) -> Iterator[tuple[PanelApp, tk.Tk]]:
    monkeypatch.setenv("ARGUS_COLLECTOR_HOME", str(tmp_path))
    root = make_tk_root()
    try:
        yield contract.create_app(root), root
    finally:
        root.destroy()


def test_each_company_starts_its_own_table_and_count(app: tuple[PanelApp, tk.Tk]) -> None:
    panel, root = app
    collect, view = panel.collect, panel.view.collect
    for name in ("A One", "A Two", "A Three"):
        collect._on_walk_event(contact(name))
    collect._on_walk_event(walk.WalkEvent(walk.EVENT_DONE, detail="frontier_exhausted"))
    assert view.row_count() == 3, "the finished company's rows stay until the next one"
    collect._on_walk_event(walk.WalkEvent("page", url="http://y.example/", page_no=1))
    for name in ("B One", "B Two"):
        collect._on_walk_event(contact(name))
    root.update()
    assert view.row_count() == 2
    assert view.found_label.cget("text") == "Löydetty: 2 yhteystietoa"


def test_the_country_line_stays_next_to_the_count(app: tuple[PanelApp, tk.Tk]) -> None:
    """`Maa: FI (vaihdettu en-br → en-fi)` stays while the company is walked."""
    panel, root = app
    collect, view = panel.collect, panel.view.collect
    country = walk.WalkEvent("step", step="country", detail="FI|en-br|en-fi|local")
    collect._on_walk_event(country)
    collect._on_walk_event(walk.WalkEvent("page", url="http://y.example/en-fi/", page_no=1))
    collect._on_walk_event(contact("Juha Kärkkäinen"))
    root.update()
    assert view.found_label.cget("text") == (
        "Löydetty: 1 yhteystietoa · Maa: FI (vaihdettu en-br → en-fi)")
    collect._on_walk_event(walk.WalkEvent(walk.EVENT_DONE, detail="goal"))
    collect._on_walk_event(contact("Next Company"))
    root.update()
    assert view.found_label.cget("text") == "Löydetty: 1 yhteystietoa", "the next company"
