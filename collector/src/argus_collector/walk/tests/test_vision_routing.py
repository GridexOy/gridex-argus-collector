"""Owner 05.10.2026: the navigation model (7b) chooses steps, the card model takes over
when 7b is missing; the vision model looks only at an uncertain bot check or a page
without DOM text, and never solves a check."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from dataclasses import replace
from typing import cast

import pytest

from argus_collector.browser import contract as browser
from argus_collector.discovery import contract as discovery
from argus_collector.models import contract as models
from argus_collector.walk import decide, service, vision
from argus_collector.walk.state import WalkState
from collector.tests.fake_model_server import FakeModelServer

URL = "https://example.fi/"
LINKS = [discovery.Candidate(0, "link", "Tuotteet", "https://example.fi/tuotteet/", "#a"),
         discovery.Candidate(1, "link", "Uutiset", "https://example.fi/uutiset/", "#b")]


class Policy:
    def __init__(self) -> None:
        self.seen: list[str] = []

    def __call__(self, system: str, user: str) -> str:
        self.seen.append(user)
        if "bot_check" in system:
            return json.dumps({"bot_check": True})
        return json.dumps({"action": "navigate", "index": 1})


class Shots:
    def screenshot(self) -> bytes:
        return b"\xff\xd8fake-jpeg"


@pytest.fixture
def fake() -> Iterator[FakeModelServer]:
    server = FakeModelServer(Policy(), missing=frozenset({"qwen2.5:7b-missing"})).start()
    yield server
    server.stop()


def walk_state(fake: FakeModelServer, nav: str = "qwen2.5:7b", vl: str = "") -> WalkState:
    cards = models.ModelConfig(fake.endpoint, "qwen2.5:14b")
    settings = service.WalkSettings(start_url=URL, model=cards)
    conn = sqlite3.connect(":memory:")
    return WalkState(
        settings, conn, models.ModelClient(cards), lambda e: None, lambda: False, "run-1",
        hosts=frozenset({"example.fi"}), focus=discovery.make_focus(["FI"], ["fi"]),
        nav_client=models.ModelClient(models.ModelConfig(fake.endpoint, nav)),
        vision_client=models.ModelClient(models.ModelConfig(fake.endpoint, vl)) if vl else None,
    )


def page(text: str, hint: bool = False) -> browser.PageState:
    return browser.PageState(URL, "Etusivu", "<html></html>", text, LINKS, challenge_hint=hint)


def choose(walk: WalkState, text: str) -> service.Action:
    wb = cast(browser.WalkBrowser, Shots())
    return decide.decide(walk, wb, page(text), text)


def test_the_navigation_model_chooses_the_step(fake: FakeModelServer) -> None:
    action = choose(walk_state(fake), "Etusivu. " * 20)
    assert action.source == "model:qwen2.5:7b"
    assert [r["model"] for r in fake.requests] == ["qwen2.5:7b"]


def test_the_card_model_takes_over_when_7b_is_not_pulled(fake: FakeModelServer) -> None:
    walk = walk_state(fake, nav="qwen2.5:7b-missing")
    assert choose(walk, "Etusivu. " * 20).source == "model:qwen2.5:14b"
    assert walk.nav_client is None, "not asked again in this run"


def test_a_page_without_dom_text_goes_to_the_vision_model(fake: FakeModelServer) -> None:
    walk = walk_state(fake, vl="qwen2.5-vl:7b")
    action = choose(walk, " ")
    assert action.source == "model:qwen2.5-vl:7b"
    sent = fake.requests[-1]["messages"][1]["content"]
    assert sent[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert choose(walk, "Etusivu. " * 20).source == "cache", "the same menu: the cached choice"
    walk.menu_cache.clear()
    assert choose(walk, "Etusivu. " * 20).source == "model:qwen2.5:7b", "text: no screenshot"


def test_vision_only_classifies_an_uncertain_bot_check(fake: FakeModelServer) -> None:
    walk = walk_state(fake, vl="qwen2.5-vl:7b")
    wb = cast(browser.WalkBrowser, Shots())
    assert vision.is_bot_check(walk, wb, page("Checking", hint=True))
    assert not vision.is_bot_check(walk, wb, page("Checking", hint=False)), "no sign: no call"
    sure = replace(page("Just a moment", hint=True), challenge=True)
    assert not vision.is_bot_check(walk, wb, sure), "the DOM is sure: no call"
    assert len(fake.requests) == 1
