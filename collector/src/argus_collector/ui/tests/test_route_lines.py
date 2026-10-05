"""Resurssit: the routed models and whether they are pulled."""

from __future__ import annotations

from argus_collector.ui import repository
from argus_collector.ui.route_lines import RouteHealth, route_line


def test_route_line_names_the_missing_model() -> None:
    msgs = repository.load_messages()
    ok = (RouteHealth("navigation", "qwen2.5:7b", True),)
    assert route_line(msgs, ok) == ("Reititys: säännöt ensin · navigointi qwen2.5:7b", "ok")
    mixed = (*ok, RouteHealth("vision", "qwen2.5-vl:7b", False))
    text, level = route_line(msgs, mixed) or ("", "")
    assert text.endswith("kuvakaappaus qwen2.5-vl:7b puuttuu") and level == "warn"
    assert route_line(msgs, ()) is None
