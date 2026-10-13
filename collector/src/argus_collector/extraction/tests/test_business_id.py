"""K14: the company's registration number, only with a right check digit."""

from __future__ import annotations

from argus_collector.extraction import contract as extraction


def test_a_labelled_y_tunnus_is_read_with_its_line() -> None:
    text = "Fixture Oy\nY-tunnus: 1234567-1\nPuh. 09 123 4567\n"
    found = extraction.business_id(text)
    assert found is not None
    assert found.value == "1234567-1"
    assert found.quote == "Y-tunnus: 1234567-1"
    assert text[found.start:found.end] == found.quote, "the quote is the line of the page"
    assert found.value in found.quote, "ARGUS checks that the quote holds the value"


def test_a_vat_number_gives_the_same_company_number() -> None:
    found = extraction.business_id("VAT FI12345671\n")
    assert found is not None and found.value == "1234567-1"


def test_a_wrong_check_digit_is_not_a_business_id() -> None:
    assert extraction.business_id("Y-tunnus 1234567-9\n") is None
    assert extraction.business_id("Tilausnumero 1234567-9\n") is None


def test_a_bare_number_without_a_label_is_not_one() -> None:
    """A phone number or an order code must never pass for a registration number."""
    assert extraction.business_id("Soita 1234567-1 heti\n") is None
    assert extraction.business_id("09 123 4567\n") is None
