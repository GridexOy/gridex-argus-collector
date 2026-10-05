"""Owner 05.10.2026 (Beckhoff): Worldwide -> Finland -> /fi-fi/ by rules, other
countries never offered, contact links followed without the model, menu cache."""

from __future__ import annotations

from dataclasses import replace

from argus_collector.browser import contract as browser
from argus_collector.discovery import contract as discovery
from argus_collector.walk import rules, service, structure
from argus_collector.walk.tests.test_structure import cand, state

BASE = "https://www.example.com"
GLOBAL = f"{BASE}/en-en/company/global-presence/"


def at(url: str, cands: list[discovery.Candidate]) -> browser.PageState:
    return browser.PageState(url, "Page", "<html></html>", "text", cands)


def link(i: int, text: str, path: str) -> discovery.Candidate:
    return cand(i, text, kind="link", href=BASE + path)


def test_worldwide_tab_is_opened_while_finland_is_not_on_the_page() -> None:
    walk = state()
    tabs = [cand(0, "Germany", "tab", "on"), cand(1, "Beckhoff Worldwide", "tab", "off")]
    action = structure.structural_action(walk, at(GLOBAL, tabs))
    assert action is not None and action.candidate is not None
    assert (action.kind, action.candidate.text) == (service.ACTION_CLICK, "Beckhoff Worldwide")
    assert structure.structural_action(walk, at(GLOBAL, tabs)) is None, "once per page"
    named = [*tabs, cand(2, "Finland", "expand", "off"), cand(3, "Sweden", "expand", "off")]
    assert structure.structural_action(state(), at(GLOBAL, named[1:2] + named[2:3])) is None


def test_other_countries_are_never_offered_unless_the_seed_is_local() -> None:
    cands = [cand(0, "Germany", "tab", "on"), link(1, "www.beckhoff.com/de-de", "/de-de/"),
             link(2, "Deutsch", "/de-de/"), link(3, "Products", "/en-en/products/"),
             link(4, "Suomi", "/fi-fi/")]
    offered = structure.offered(state(), cands)
    assert [c.text for c in offered] == ["Products", "Suomi"]
    local = state()
    assert local.focus is not None
    local.focus = replace(local.focus, local_seed=True)
    assert len(structure.offered(local, cands)) == 5, "a local seed walks other versions after"


def test_rules_country_version_then_finder_then_contact() -> None:
    walk = state()
    home = [link(0, "Products", "/en-en/products/"), link(1, "Contact", "/en-en/contact/"),
            link(2, "Global presence", "/en-en/company/global-presence/")]
    first = rules.rule_action(walk, at(f"{BASE}/en-en/", home), home)
    assert first is not None and first.candidate is not None
    assert (first.candidate.text, first.source) == ("Global presence", "rule")
    section = [*home, link(3, "www.beckhoff.com/fi-fi", "/fi-fi/")]
    version = rules.rule_action(walk, at(GLOBAL, section), section)
    assert version is not None and version.candidate is not None
    assert version.candidate.href == BASE + "/fi-fi/"
    local = [link(0, "Tuotteet", "/fi-fi/tuotteet/"),
             link(1, "Yhteystiedot", "/fi-fi/yhteystiedot/")]
    contact = rules.rule_action(walk, at(f"{BASE}/fi-fi/", local), local)
    assert contact is not None and contact.candidate is not None
    assert contact.candidate.text == "Yhteystiedot", "the /fi/ bonus alone is no rule"
    walk.mark_visited(BASE + "/fi-fi/yhteystiedot/")
    assert rules.rule_action(walk, at(f"{BASE}/fi-fi/", local), local) is None


def test_menu_cache_reuses_the_choice_while_it_is_unvisited() -> None:
    walk = state()
    menu = [link(0, "Products", "/en-en/products/"), link(1, "Careers", "/en-en/careers/")]
    key = rules.menu_key(walk, menu)
    assert key == rules.menu_key(walk, list(reversed(menu))), "order does not matter"
    rules.remember(walk, key, service.Action(service.ACTION_NAVIGATE, menu[1]))
    again = rules.cached_action(walk, key, menu)
    assert again is not None and again.source == "cache" and again.candidate == menu[1]
    walk.mark_visited(BASE + "/en-en/careers/")
    assert rules.cached_action(walk, key, menu) is None
