"""Discovery rules: hosts (K7), social networks (K8), ranking, URL keys."""

from __future__ import annotations

from argus_collector.discovery import contract
from argus_collector.discovery.contract import Candidate


def link(i: int, text: str, href: str) -> Candidate:
    return Candidate(i, "link", text, href, f'[data-argus-idx="{i}"]')


def test_normalize_url() -> None:
    assert contract.normalize_url("HTTPS://WWW.Example.com:443/a/#x") == "https://www.example.com/a"
    assert contract.normalize_url("http://h:8765/") == "http://h:8765/"
    assert contract.normalize_url("http://h/team?page=2") == "http://h/team?page=2"


def test_hosts_exact_match_no_suffix_comparison() -> None:
    hosts = contract.approved_hosts_for("https://www.sandvik.com/", "https://home.sandvik/")
    assert hosts == frozenset({"sandvik.com", "home.sandvik"})
    assert contract.is_allowed_url("https://sandvik.com/contact", hosts)
    assert contract.is_allowed_url("https://www.sandvik.com/contact", hosts)
    assert not contract.is_allowed_url("https://katsa.sandvik.com/contact", hosts)
    assert not contract.is_allowed_url("https://notsandvik.com/", hosts)
    assert not contract.is_allowed_url("mailto:a@sandvik.com", hosts)
    assert not contract.is_allowed_url("https://sandvik.com/brochure.PDF", hosts)


def test_social_networks_never_allowed() -> None:
    hosts = frozenset({"linkedin.com", "x.com"})
    assert contract.is_social_url("https://www.linkedin.com/company/x")
    assert contract.is_social_url("https://fi.linkedin.com/in/anna")
    assert not contract.is_allowed_url("https://linkedin.com/company/x", hosts)
    assert not contract.is_allowed_url("https://x.com/company", hosts)
    assert not contract.is_social_url("https://example.com/linkedin.com")


def test_score_prefers_contact_words_and_penalises_noise() -> None:
    assert contract.score_link("Yhteystiedot", "/yhteystiedot") > contract.score_link(
        "Tuotteet", "/tuotteet"
    )
    assert contract.score_link("Privacy policy", "/privacy") < 0
    assert contract.score_link("Seuraava sivu", "/team-2.html") > 0


def test_rank_candidates_filters_sorts_and_keeps_buttons() -> None:
    hosts = frozenset({"h"})
    cands = [
        link(0, "Home", "http://h/index.html"),
        link(1, "Products", "http://h/products.html"),
        link(2, "Contact", "http://h/contact.html"),
        link(3, "LinkedIn", "https://linkedin.com/company/h"),
        link(4, "Contact again", "http://h/contact.html#top"),
        link(5, "Other site", "http://other/"),
        Candidate(6, "button", "Show contacts", "", '[data-argus-idx="6"]'),
    ]
    ranked = contract.rank_candidates(cands, {"http://h/index.html"}, hosts)
    assert [c.index for c in ranked] == [2, 1, 6]


def test_page_key_uses_normalised_url_and_hash_prefix() -> None:
    key = contract.page_key("http://H/a/#frag", "ab" * 32)
    assert key == "http://h/a#" + "ab" * 8
