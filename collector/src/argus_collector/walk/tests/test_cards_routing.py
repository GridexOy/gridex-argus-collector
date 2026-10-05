"""Owner 05.10.2026: the card model (14b) only when JSON-LD and the rules leave people unread."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator

import pytest

from argus_collector.browser import contract as browser
from argus_collector.discovery import contract as discovery
from argus_collector.evidence import contract as evidence
from argus_collector.extraction import contract as extraction
from argus_collector.models import contract as models
from argus_collector.walk import cards, service
from argus_collector.walk.state import WalkState
from argus_collector.walk.tests.fake_policy import GoldPolicy
from collector.tests.fake_model_server import FakeModelServer

ANNA = {"name": "Anna Virtanen", "title": "Myyntijohtaja", "phone": "040 123 4567",
        "email": "anna.virtanen@example.fi"}
CARD = "Anna Virtanen\nMyyntijohtaja\n040 123 4567\nanna.virtanen@example.fi\n"
JSONLD = ('<script type="application/ld+json">{"@type": "Organization", "employee": [{"@type":'
          ' "Person", "name": "Anna Virtanen", "jobTitle": "Myyntijohtaja", "telephone":'
          ' "040 123 4567", "email": "mailto:anna.virtanen@example.fi"}]}</script>')


@pytest.fixture
def fake() -> Iterator[FakeModelServer]:
    server = FakeModelServer(GoldPolicy([ANNA])).start()
    yield server
    server.stop()


def walk_state(fake: FakeModelServer) -> WalkState:
    config = models.ModelConfig(fake.endpoint, "qwen2.5:14b")
    settings = service.WalkSettings(start_url="https://example.fi/", model=config)
    conn = sqlite3.connect(":memory:")
    return WalkState(settings, conn, models.ModelClient(config), lambda e: None, lambda: False,
                     "run-1", hosts=frozenset({"example.fi"}),
                     focus=discovery.make_focus(["FI"], ["fi"]))


def read(walk: WalkState, url: str, title: str, body: str, html: str = "") -> list[str]:
    text = evidence.canonical_text(body)
    page = browser.PageState(url, title, f"<html><body>{html}</body></html>", body, [])
    channels = extraction.extract_channels(page.html, text, "FI")
    found = cards.read(walk, page, text, channels, [], "FI")
    return [c.name.value for c in found]


def test_jsonld_people_need_no_model(fake: FakeModelServer) -> None:
    walk = walk_state(fake)
    assert read(walk, "https://example.fi/johto/", "Johto", CARD, JSONLD) == ["Anna Virtanen"]
    assert (walk.timing.cards, fake.requests) == ("jsonld", [])


def test_a_page_without_personal_channels_is_skipped(fake: FakeModelServer) -> None:
    walk = walk_state(fake)
    body = "Tuotteet\nVaihde 09 123 4500\ninfo@example.fi\n"
    assert read(walk, "https://example.fi/tuotteet/", "Tuotteet", body) == []
    assert (walk.timing.cards, fake.requests) == ("skip", [])


def test_a_personal_channel_goes_to_the_card_model(fake: FakeModelServer) -> None:
    walk = walk_state(fake)
    assert read(walk, "https://example.fi/tiimi/", "Tiimi", CARD) == ["Anna Virtanen"]
    assert walk.timing.cards == "model:qwen2.5:14b" and len(fake.requests) == 1
    assert read(walk, "https://example.fi/tiimi/?tab=2", "Tiimi", CARD) == ["Anna Virtanen"]
    assert walk.timing.cards == "cache" and len(fake.requests) == 1, "same text: no new call"


def test_a_contact_page_goes_to_the_model_even_with_generic_channels(
    fake: FakeModelServer,
) -> None:
    walk = walk_state(fake)
    body = "Yhteystiedot\nVaihde 09 123 4500\ninfo@example.fi\n"
    read(walk, "https://example.fi/yhteystiedot/", "Yhteystiedot", body)
    assert len(fake.requests) == 1
