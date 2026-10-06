"""Keruu lines of the goal rule and of an address built from a stated pattern (06.10.2026)."""

from __future__ import annotations

import pytest

from argus_collector.extraction.contract import Contact, VerifiedField
from argus_collector.ui import repository, walk_lines
from argus_collector.walk.contract import LOCATOR_PATTERN, WalkEvent


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


def test_an_address_of_the_stated_pattern_reads_oletettu(msgs: repository.Messages) -> None:
    name = VerifiedField("Jari Mäkelä", "Jari Mäkelä", 0, 11, "text")
    quote = "Our e-mail addresses are the following: firstname.lastname@reimax.example"
    email = VerifiedField("jari.makela@reimax.example", quote, 20, 20 + len(quote),
                          LOCATOR_PATTERN)
    event = WalkEvent("contact", url="http://reimax/contact/",
                      contact=Contact(name, None, None, email))
    assert walk_lines.contact_row(event, msgs)[3] == "oletettu: jari.makela@reimax.example"
    printed = WalkEvent("contact", url="u", contact=Contact(
        name, None, None, VerifiedField("j@x.example", "j@x.example", 0, 11, "href:mailto")))
    assert walk_lines.contact_row(printed, msgs)[3] == "j@x.example"
