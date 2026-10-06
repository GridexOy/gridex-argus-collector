"""The goal rule (owner 06.10.2026): asked before every next action."""

from __future__ import annotations

import json
from pathlib import Path

from argus_collector.extraction.contract import Contact, VerifiedField
from argus_collector.walk import contract, goal, service
from argus_collector.walk.tests.conftest import GOLD as GOLD_FILE
from argus_collector.walk.tests.conftest import settings_for
from argus_collector.walk.tests.fake_policy import GoldPolicy
from collector.tests.fake_model_server import FakeModelServer

GOLD = json.loads(GOLD_FILE.read_text(encoding="utf-8"))


def field(value: str, locator: str = "text") -> VerifiedField:
    return VerifiedField(value, value, 0, len(value), locator)


def person(name: str, title: str | None, phone: str | None = None,
           email: str | None = None) -> Contact:
    return Contact(field(name), field(title) if title else None,
                   field(phone) if phone else None, field(email) if email else None)


def test_sales_and_marketing_titles_in_the_languages_of_the_sites() -> None:
    for title in ("Myyntipäällikkö", "Key Account Manager", "Area Sales Manager Nordics",
                  "Markkinointipäällikkö", "Exportleiter Nordeuropa", "Vertrieb Inland",
                  "Säljchef", "Marketing Manager International", "Vientipäällikkö"):
        assert goal.is_sales(title), title
    for title in ("Toimitusjohtaja", "Accountant", "HR Manager", "Service Manager", "CFO"):
        assert not goal.is_sales(title), title


def test_a_sales_person_with_a_printed_channel_is_the_goal() -> None:
    tally = goal.Tally()
    goal.note(tally, "a", person("Anna", "Sales Manager", email="a@x.example"), False, 2)
    assert goal.verdict(tally, 2) == service.END_GOAL
    assert (len(tally.people), tally.channels) == (1, 1)


def test_an_address_from_a_pattern_is_not_a_printed_channel() -> None:
    tally = goal.Tally()
    goal.note(tally, "a", person("Anna", "Sales Manager", email="a@x.example"), True, 2)
    assert goal.verdict(tally, 2) is None and tally.channels == 0


def test_people_without_the_goal_allow_two_more_pages() -> None:
    tally = goal.Tally()
    assert goal.verdict(tally, 1) is None, "nobody read: no reason to stop"
    goal.note(tally, "c", person("Carl", "Toimitusjohtaja", phone="+358401"), False, 2)
    goal.note(tally, "d", person("Dora", "Sales Manager"), False, 2)  # no channel
    assert goal.verdict(tally, 2) is None
    assert goal.verdict(tally, 3) is None
    assert goal.verdict(tally, 4) == service.END_GOAL_PAGES
    goal.note(tally, "d", person("Dora", "Sales Manager", phone="+358402"), False, 3)
    assert goal.verdict(tally, 3) == service.END_GOAL, "a later page gives Dora her phone"


def test_found_team_links_are_still_read_after_the_goal(site: str, tmp_path: Path) -> None:
    """Owner 06.10.2026 (0.4.8.7): the goal on contact.html, then the found team link."""
    fake = FakeModelServer(GoldPolicy(GOLD["persons"])).start()
    events: list[contract.WalkEvent] = []
    try:
        summary = contract.run_walk(settings_for(site, fake, tmp_path, stop_at_goal=True),
                                    events.append, lambda: False)
    finally:
        fake.stop()
    assert summary.end_reason == service.END_GOAL
    visited = [u.rsplit("/", 1)[-1] for u in summary.visited]
    assert "contact.html" in visited and "team.html" in visited, visited
    goal_step = [e for e in events if e.kind == "step" and e.step == "goal"]
    assert len(goal_step) == 1 and goal_step[0].people >= 5, "3 on contact.html + the team pages"
