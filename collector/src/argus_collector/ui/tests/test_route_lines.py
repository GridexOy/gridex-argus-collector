"""Resurssit: who decides and who reads (6.1: the rules and one card model)."""

from __future__ import annotations

from argus_collector.ui import repository
from argus_collector.ui.route_lines import RouteHealth, route_line


def test_the_route_line_names_the_rules_and_the_card_model() -> None:
    msgs = repository.load_messages()
    pulled = (RouteHealth("qwen2.5:14b-instruct", True),)
    assert route_line(msgs, pulled) == ("Reititys: säännöt → qwen2.5:14b-instruct", "ok")
    text, level = route_line(msgs, (RouteHealth("qwen2.5:14b-instruct", False),)) or ("", "")
    assert text == "Reititys: säännöt → qwen2.5:14b-instruct puuttuu" and level == "warn"
    assert route_line(msgs, ()) is None, "no line before the diagnostics have run"
