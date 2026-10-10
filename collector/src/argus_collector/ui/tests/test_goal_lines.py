"""Keruu lines of the goal rule and of the address column (06.10.2026, 10.10.2026)."""

from __future__ import annotations

import pytest

from argus_collector.extraction.contract import Contact, VerifiedField
from argus_collector.ui import repository, walk_lines
from argus_collector.walk.contract import WalkEvent


@pytest.fixture
def msgs() -> repository.Messages:
    return repository.load_messages()


def test_the_goal_line_at_the_step_and_at_the_end(msgs: repository.Messages) -> None:
    step = WalkEvent("step", step="goal", people=14, channels=14)
    assert walk_lines.walk_event_line(msgs, step) == (
        "Tavoite saavutettu: 14 henkilöä, 14 kanavaa", "ok")
    done = WalkEvent("done", detail="completed", step="goal", people=3, channels=6)
    assert walk_lines.walk_event_line(msgs, done) == (
        "Tavoite saavutettu: 3 henkilöä, 6 kanavaa", "ok")
    pages = WalkEvent("done", step="goal_pages", people=2, channels=0)
    text, level = walk_lines.goal_line(msgs, pages) or ("", "")
    assert text.endswith(": 2 henkilöä, 0 kanavaa") and level == "info"
    assert walk_lines.goal_line(msgs, WalkEvent("done", detail="completed")) is None


def test_every_address_in_the_table_is_printed_on_the_page(msgs: repository.Messages) -> None:
    """0.4.8.11: no address is built from a pattern, so none is marked `oletettu`."""
    name = VerifiedField("Jari Mäkelä", "Jari Mäkelä", 0, 11, "text")
    printed = WalkEvent("contact", url="u", contact=Contact(
        name, None, None, VerifiedField("j@x.example", "j@x.example", 0, 11, "href:mailto")))
    assert walk_lines.contact_row(printed, msgs)[3] == "j@x.example"
    assert "collecting.inferred" not in msgs.keys(), "the oletettu line went with the feature"
