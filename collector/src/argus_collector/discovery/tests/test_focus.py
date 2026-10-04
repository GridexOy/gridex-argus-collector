"""Exhibition-country focus: language switches, local office, export people."""

from __future__ import annotations

import pytest

from argus_collector.discovery import contract

FI = contract.make_focus(["FI"], ["fi", "en"])


def cand(index: int, text: str, href: str) -> contract.Candidate:
    return contract.Candidate(index, "link", text, href, f'[data-argus-idx="{index}"]')


@pytest.mark.parametrize(
    ("text", "href", "expected"),
    [
        ("Suomi", "https://x.example/fi/", "fi"),
        ("FI", "https://x.example/?lang=fi", "fi"),
        ("Svenska", "https://x.example/sv/", "sv"),
        ("Français", "https://x.example/fr/", "fr"),
        ("Yhteystiedot", "https://x.example/fi/yhteystiedot.html", "fi"),
        ("Products", "https://x.example/de-de/produkte", "de"),
        ("Contact", "https://x.example/contact.html", None),
    ],
)
def test_link_language(text: str, href: str, expected: str | None) -> None:
    assert contract.link_language(text, href) == expected


def test_no_priorities_means_no_focus() -> None:
    assert contract.make_focus([], []) is None
    assert contract.focus_brief(None) == ""


def test_finnish_version_and_finland_office_rank_first() -> None:
    hosts = frozenset({"nordtec.localhost"})
    focus = FI.with_native("en") if FI else None
    links = [
        cand(0, "Products", "http://nordtec.localhost/products.html"),
        cand(1, "Contact", "http://nordtec.localhost/contact.html"),
        cand(2, "Svenska", "http://nordtec.localhost/sv/"),
        cand(3, "Suomi", "http://nordtec.localhost/fi/"),
        cand(4, "Finland office (Helsinki)", "http://nordtec.localhost/office.html"),
    ]
    ranked = [c.text for c in contract.rank_candidates(links, set(), hosts, focus)]
    assert ranked[:3] == ["Suomi", "Finland office (Helsinki)", "Contact"]
    assert ranked[-1] == "Svenska"
    plain = [c.text for c in contract.rank_candidates(links, set(), hosts)]
    assert plain[0] == "Contact", "without a focus the ranking is unchanged"


def test_company_without_local_office_goes_to_export_people() -> None:
    hosts = frozenset({"vogel.localhost"})
    focus = FI.with_native("de") if FI else None
    links = [
        cand(0, "Produkte", "http://vogel.localhost/produkte.html"),
        cand(1, "Kontakt", "http://vogel.localhost/kontakt.html"),
        cand(2, "Vertrieb International", "http://vogel.localhost/export.html"),
        cand(3, "English", "http://vogel.localhost/en/"),
        cand(4, "Français", "http://vogel.localhost/fr/"),
    ]
    ranked = [c.text for c in contract.rank_candidates(links, set(), hosts, focus)]
    assert ranked[0] == "Vertrieb International"
    assert ranked.index("English") < ranked.index("Produkte")
    assert ranked[-1] == "Français", "a third language comes last"


def test_brief_names_country_languages_and_export_fallback() -> None:
    assert FI is not None
    brief = contract.focus_brief(FI.with_native("de"))
    assert "Finland (FI)" in brief and "fi, en" in brief
    assert "export, Nordic" in brief and "in de or in English" in brief
