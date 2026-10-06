"""Kontaktit 05.10.2026 and owner 06.10.2026: no circles, no model where the rules read people.

A link that led back to a walked page (a WPML redirect) is walked; a page read before is
never the target again; a button pressed in a page state is not offered again; six
actions without a new page state end the walk `no_progress`; a page whose people the
rules read gets its next step from the rules; an unvisited link is no reason not to finish.
"""

from __future__ import annotations

import sqlite3
from typing import Any, cast

from argus_collector.browser import contract as browser
from argus_collector.discovery import contract as discovery
from argus_collector.discovery.contract import Candidate
from argus_collector.models import contract as models
from argus_collector.walk import decide, page, service
from argus_collector.walk.service import Action
from argus_collector.walk.state import MAX_STALLED, WalkState
from argus_collector.walk.tests.test_walk_job import RecordingSink

SITE = "https://example.fi/"
NO_BROWSER = cast(Any, None)  # these decisions never touch the browser


def state(job: bool = True) -> WalkState:
    config = models.ModelConfig("http://127.0.0.1:9", "unreachable")
    settings = service.WalkSettings(start_url=SITE, model=config)
    sink = RecordingSink() if job else None
    return WalkState(settings, sqlite3.connect(":memory:"), models.ModelClient(config),
                     lambda e: None, lambda: False, "run-1", sink, hosts=frozenset({"example.fi"}))


def link(i: int, text: str, path: str) -> Candidate:
    return Candidate(i, "link", text, SITE + path, f'[data-argus-idx="{i}"]')


def button(i: int, text: str) -> Candidate:
    return Candidate(i, "button", text, "", f'[data-argus-idx="{i}"]')


def at(path: str, *cands: Candidate) -> browser.PageState:
    return browser.PageState(SITE + path, "t", "<html></html>", "text", list(cands))


def test_a_link_that_led_to_a_walked_page_is_walked_too() -> None:
    walk = state()
    walk.mark_visited(SITE + "fi/ota-yhteytta/")
    walk.arrived(SITE + "contact-us/", SITE + "fi/ota-yhteytta/")
    assert SITE.rstrip("/") + "/contact-us" in {u.rstrip("/") for u in walk.walked()}
    offered = page.ranked(walk, at("fi/", link(1, "Contact us", "contact-us/")))
    assert offered == [], "the WPML alias is not offered again"


def test_a_link_that_led_elsewhere_is_never_followed_again() -> None:
    """Owner 06.10.2026: no second visit whatever the redirect; off the hosts: a gap."""
    walk = state()
    walk.arrived(SITE + "yhteystiedot/", SITE + "fi/yhteystiedot/")
    assert walk.cp.redirected == [discovery.normalize_url(SITE + "yhteystiedot/")]
    walk.arrived(SITE + "shop/", "https://shop.example.com/")
    assert len(walk.cp.redirected) == 1, "a link that left the approved hosts is no alias"


def test_a_pressed_button_is_not_offered_in_the_same_state() -> None:
    walk = state()
    walk.current_key = "k1"
    walk.clicked["k1"] = {'[data-argus-idx="2"]'}
    shown = page.ranked(walk, at("tiimi/", button(2, "Myynti"), button(3, "Huolto")))
    assert [c.text for c in shown] == ["Huolto"]
    walk.current_key = "k2"
    assert len(page.ranked(walk, at("tiimi/", button(2, "Myynti")))) == 1, "a new state"


def test_six_actions_without_a_new_state_end_the_walk() -> None:
    walk = state()
    walk.cp.frontier.clear()
    walk.stalled = MAX_STALLED
    decide.end_stalled(walk, SITE)
    assert walk.end_reason == service.END_NO_PROGRESS
    assert [(g.reason, g.resumable) for g in walk.cp.gaps] == [("no_progress", False)]


def test_a_ruled_page_takes_its_next_step_from_the_rules() -> None:
    walk = state()
    walk.ruled_urls.add(discovery.normalize_url(SITE + "yhteystiedot/"))
    here = at("yhteystiedot/", link(1, "Tuotteet", "tuotteet/"), link(2, "Referenssit", "ref/"))
    action = decide.decide(walk, NO_BROWSER, here, "text")
    assert action.kind == service.ACTION_NAVIGATE and action.source == "rules"


def test_a_page_read_before_is_never_the_target() -> None:
    walk = state()
    walk.mark_visited(SITE + "tuotteet/")
    action = decide._unread(walk, Action(service.ACTION_NAVIGATE, link(1, "x", "tuotteet/")))
    assert (action.kind, action.source) == (service.ACTION_FINISH, "read_before")


def test_the_panel_sets_the_action_budget() -> None:
    config = models.ModelConfig("http://127.0.0.1:9", "m")
    limits = service.WalkSettings(start_url=SITE, model=config, action_budget=7).run_limits()
    assert limits.actions == 7
