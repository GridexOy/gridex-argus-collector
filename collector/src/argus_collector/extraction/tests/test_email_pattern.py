"""An address pattern a page states (owner 06.10.2026, Reimax): found, applied, no channel."""

from __future__ import annotations

from argus_collector.extraction import contract as extraction
from argus_collector.extraction.service import PersonCard

NOTE = "Our e-mail addresses are the following: firstname.lastname@reimax.example"


def test_patterns_in_several_languages_with_their_line() -> None:
    text = "\n".join([
        "Contact", NOTE, "Sähköpostit muotoa etunimi.sukunimi@firma.example",
        "E-Mail: [Vorname]_[Nachname]@firma.example", "Mail: efternamn-fornamn@ab.example",
    ])
    found = extraction.email_patterns(text)
    assert [(p.value, p.separator, p.last_first) for p in found] == [
        ("firstname.lastname@reimax.example", ".", False),
        ("firstname.lastname@firma.example", ".", False),
        ("firstname_lastname@firma.example", "_", False),
        ("lastname-firstname@ab.example", "-", True),
    ]
    assert found[0].quote == NOTE and text[found[0].start:found[0].end] == NOTE


def test_an_address_per_full_name_in_plain_letters() -> None:
    pattern = extraction.email_patterns(NOTE)[0]
    assert extraction.pattern_address(pattern, "Jari Mäkelä") == "jari.makela@reimax.example"
    assert extraction.pattern_address(pattern, "Anna-Kaisa Lähde") == (
        "anna-kaisa.lahde@reimax.example")
    assert extraction.pattern_address(pattern, "Jörg Groß") == "jorg.gross@reimax.example"
    assert extraction.pattern_address(pattern, "Matti Juhani Virtanen") == (
        "matti.virtanen@reimax.example"), "first and last word"
    assert extraction.pattern_address(pattern, "Madonna") is None
    other = extraction.email_patterns("lastname.firstname@x.example")[0]
    assert extraction.pattern_address(other, "Päivi Öhman") == "ohman.paivi@x.example"


def test_a_pattern_is_never_a_channel_or_a_persons_email() -> None:
    text = f"{NOTE}\nJari Mäkelä\nSales Director\n+358 40 551 2002\ninfo@reimax.example"
    channels = extraction.extract_channels(
        '<a href="mailto:firstname.lastname@reimax.example">x</a>', text, "FI")
    assert {c.value for c in channels if c.kind == "email"} == {"info@reimax.example"}
    card = PersonCard("Jari Mäkelä", "Sales Director", "+358 40 551 2002",
                      "firstname.lastname@reimax.example")
    contact = extraction.verify_card(card, text, channels, "FI")
    assert contact is not None and contact.email is None and contact.phone is not None


def test_no_pattern_in_ordinary_addresses() -> None:
    text = "matti.virtanen@firma.example, first@firma.example, sales@firma.example"
    assert extraction.email_patterns(text) == []
