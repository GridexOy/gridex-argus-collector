"""Normalisation rules: phones, emails, obfuscations, names."""

from __future__ import annotations

import pytest

from argus_collector.normalization import contract


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("040 123 4567", "+358401234567"),
        ("+358 40 123 4567", "+358401234567"),
        ("+358 (0)40 1234567", "+358401234567"),
        ("00358401234567", "+358401234567"),
        ("tel:+358401234567", "+358401234567"),
        ("020 123 4560 ext. 12", "+358201234560"),
        ("(09) 123 4567", "+35891234567"),
        ("12345", None),
        ("1987", None),
        ("abc", None),
    ],
)
def test_normalize_phone(raw: str, expected: str | None) -> None:
    assert contract.normalize_phone(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Anna.Virtanen@Fixture.Example", "anna.virtanen@fixture.example"),
        ("mailto:info@fixture.example?subject=x", "info@fixture.example"),
        ("pekka.salo (at) fixture.example", "pekka.salo@fixture.example"),
        ("pekka.salo[at]fixture[dot]example", "pekka.salo@fixture.example"),
        ("pekka.salo at fixture dot example", "pekka.salo@fixture.example"),
        ("not an email", None),
        ("a@b", None),
    ],
)
def test_normalize_email(raw: str, expected: str | None) -> None:
    assert contract.normalize_email(raw) == expected


def test_decode_cfemail() -> None:
    address = "sari@fixture.example"
    key = 0x5A
    encoded = f"{key:02x}" + "".join(f"{ord(c) ^ key:02x}" for c in address)
    assert contract.decode_cfemail(encoded) == address
    assert contract.decode_cfemail("zz") is None
    assert contract.decode_cfemail("5a") is None


def test_find_emails_and_phones_in_text() -> None:
    text = (
        "Sales: anna.virtanen@fixture.example, puh. 040 123 4567. "
        "Pekka: pekka.salo (at) fixture.example, +358 50 765 4321. Founded 1987."
    )
    assert contract.find_emails(text) == [
        "anna.virtanen@fixture.example",
        "pekka.salo (at) fixture.example",
    ]
    assert contract.find_phones(text) == ["040 123 4567", "+358 50 765 4321"]


def test_normalize_name_and_text() -> None:
    assert contract.normalize_text("  Anna \n Virtanen ") == "Anna Virtanen"
    assert contract.normalize_name(" Anna  Virtanen ") == "Anna Virtanen"
    assert contract.normalize_name("040 123") is None
    assert contract.normalize_name("") is None
    assert contract.normalize_name("a@b.c") is None


def test_same_value() -> None:
    assert contract.same_value("phone", "040 123 4567", "+358401234567")
    assert contract.same_value("email", "A@B.example", "a@b.example")
    assert contract.same_value("text", "Sales  Director", "sales director")
    assert not contract.same_value("phone", "abc", "abc")
