"""Country labels and versions, the local seed, country lists, department order."""

from __future__ import annotations

from dataclasses import replace

import pytest

from argus_collector.discovery import contract as discovery


@pytest.mark.parametrize(("label", "code"), [
    ("Finland", "FI"), ("Suomi", "FI"), ("Suomi / Finland", "FI"), ("Finland (FI)", "FI"),
    ("FI", "FI"), ("Finland office", "FI"), ("United Kingdom", "GB"), ("UK", "GB"),
    ("Sverige", "SE"), ("Deutschland", "DE"), ("Österreich", "AT"),
    ("Sales", None), ("Hallinto", None), ("Svenska", None), ("EN", None), ("fi", None),
    ("Germany Austria Switzerland", None), ("Our offices in Finland and abroad", None),
])
def test_label_country(label: str, code: str | None) -> None:
    assert discovery.label_country(label) == code


@pytest.mark.parametrize(("url", "code"), [
    ("https://www.malux.fi/", "FI"), ("https://fi.ledvance.com/", "FI"),
    ("https://www.ledvance.com/fi-fi/", "FI"), ("https://www.ledvance.com/sv-se/x", "SE"),
    ("https://www.malux.com/fi/yhteystiedot", "FI"), ("https://www.malux.com/sv/", "SE"),
    ("https://www.ledvance.com/en-int/company/contact", None), ("https://x.com/en/", None),
    ("https://x.com/", None),
])
def test_url_country(url: str, code: str | None) -> None:
    assert discovery.url_country(url) == code


def test_local_seed() -> None:
    assert discovery.is_local_seed("https://www.malux.com/fi/", "FI")
    assert discovery.is_local_seed("https://www.malux.fi/", "FI")
    assert not discovery.is_local_seed("https://www.ledvance.com/", "FI")
    assert not discovery.is_local_seed("https://www.malux.se/", "FI")


def test_other_country_versions_are_walked_after_a_local_seed() -> None:
    focus = discovery.make_focus(["FI"], ["fi", "en"])
    assert focus is not None
    local = replace(focus, local_seed=True)
    se_switch = ("SE", "https://malux-se.example/sv/")
    assert discovery.strong_link(*se_switch, local), "walked after the Finnish pages"
    assert not discovery.strong_link(*se_switch, focus), "not without a local seed"
    fi_contacts = discovery.score_link("Yhteystiedot", "https://malux.example/fi/yhteystiedot",
                                       local)
    assert fi_contacts > discovery.score_link(*se_switch, local), "Finnish first"
    assert discovery.strong_link("Kontakt", "https://malux-se.example/sv/kontakt", local)
    assert discovery.strong_link("www.ledvance.com/fi-fi", "https://ledvance.example/fi-fi/",
                                 focus), "the local site version"


def _cand(i: int, text: str, kind: str = "button", options: tuple[str, ...] = ()
          ) -> discovery.Candidate:
    return discovery.Candidate(i, kind, text, "", f"#c{i}", options=options)


def test_country_members_need_three_countries() -> None:
    two = [_cand(0, "Suomi"), _cand(1, "Sverige"), _cand(2, "Products")]
    assert discovery.country_members(two) == {}
    many = [_cand(0, "Austria"), _cand(1, "Finland"), _cand(2, "France"), _cand(3, "Sales")]
    members = discovery.country_members(many)
    assert set(members) == {"AT", "FI", "FR"} and members["FI"][0].text == "Finland"
    select = _cand(4, "Choose your country", "select", ("", "Austria", "Finland", "Germany"))
    assert set(discovery.country_members([select])) == {"AT", "FI", "DE"}


def test_department_rank_sales_first_support_last() -> None:
    ranks = {label: discovery.department_rank(label) for label in (
        "Myynti", "Markkinointi", "Sales & Marketing", "Försäljning", "ATEX/Teollisuus",
        "Valaistus", "Hallinto", "Varasto", "Logistiikka", "IT")}
    assert ranks["Myynti"] == ranks["Markkinointi"] == ranks["Sales & Marketing"] == 0
    assert ranks["Försäljning"] == 0
    assert ranks["ATEX/Teollisuus"] == ranks["Valaistus"] == 1
    assert ranks["Hallinto"] == ranks["Varasto"] == ranks["Logistiikka"] == ranks["IT"] == 2
