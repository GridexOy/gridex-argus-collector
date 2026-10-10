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
        ("etunimi.sukunimi@firma.example", ".", False),
        ("[Vorname]_[Nachname]@firma.example", "_", False),
        ("efternamn-fornamn@ab.example", "-", True),
    ], "the value is the pattern as printed, so its quote contains it"
    for found_pattern in found:
        assert found_pattern.value in found_pattern.quote
    assert found[0].quote == NOTE and text[found[0].start:found[0].end] == NOTE


def test_no_address_is_derived_from_a_pattern() -> None:
    """0.4.8.11 (owner 10.10.2026): a derived address stands in no line of the page,
    so no quote could contain it and ARGUS refuses it (`value_not_in_quote`)."""
    assert not hasattr(extraction, "pattern_address")


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
