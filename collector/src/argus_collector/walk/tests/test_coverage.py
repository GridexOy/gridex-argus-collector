"""Declared directory sizes and own-brand links on unapproved hosts."""

from __future__ import annotations

import sqlite3
from typing import cast

from argus_collector.discovery import contract as discovery
from argus_collector.models import contract as models
from argus_collector.walk import coverage, service
from argus_collector.walk.state import WalkState


def test_declared_total() -> None:
    assert coverage.declared_total("Henkilöstö\n37 henkilöä") == 37
    assert coverage.declared_total("Showing 1-10 of 42 results") == 42
    assert coverage.declared_total("Näytetään 1–10 / 25") == 25
    assert coverage.declared_total("Founded 1987, 120 years of tradition") == 0


def test_foreign_brand_link_is_a_gap_once() -> None:
    settings = service.WalkSettings(start_url="https://www.ledvance.com/",
                                    model=models.ModelConfig("http://x/v1", "m"))
    state = WalkState(settings, sqlite3.connect(":memory:"), cast(models.ModelClient, None),
                      lambda e: None, lambda: False, "run", hosts=frozenset({"ledvance.com"}),
                      focus=discovery.make_focus(["FI"], ["fi", "en"]))
    links = [
        discovery.Candidate(0, "link", "Yhteystiedot", "https://www.ledvance.fi/yhteystiedot", ""),
        discovery.Candidate(1, "link", "Contact", "https://www.ledvance.fi/contact", ""),
        discovery.Candidate(2, "link", "Contact", "https://www.partner.example/contact", ""),
        discovery.Candidate(3, "link", "Products", "https://shop.ledvance.de/p", ""),
    ]
    coverage.note_foreign_links(state, "https://www.ledvance.com/contact", links)
    assert [(g.reason, discovery.host_of(g.url)) for g in state.cp.gaps] == [
        ("domain_ownership_unresolved", "ledvance.fi")]
    assert not state.cp.gaps[0].resumable, "the owner adds the host, the walk does not"
