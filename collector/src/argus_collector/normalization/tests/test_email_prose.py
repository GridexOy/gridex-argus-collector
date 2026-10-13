"""Prose is not an address (owner 13.10.2026, from the live run of cv0.5.2.0).

Pages of real companies turned sentences into addresses: `look at it. Going` became
look@it.going and `Ampeerin (A) virran. Tehohan` became ampeerin@virran.tehohan,
because ` at ` and `(A)` were read as `@`. ARGUS refused them as `value_not_in_quote`.
A word-spelled `@` now needs a domain without spaces and a letters-only top level.
"""

from __future__ import annotations

import pytest

from argus_collector.normalization import contract as norm

PROSE = [
    "look at it. Going",
    "Ampeerin (A) virran. Tehohan",
    "Ampeerin (A) virran. Ampeeri",
    "balance @9.6",
    "Call us at 09 123 4567",
]
ADDRESSES = [
    ("info (at) reimax.fi", "info@reimax.fi"),
    ("etunimi.sukunimi(at)destia.fi", "etunimi.sukunimi@destia.fi"),
    ("heikki.raivio @ ssaoy.fi", "heikki.raivio@ssaoy.fi"),
    ("myynti [at] example [dot] fi", "myynti@example.fi"),
    ("myynti (at) example (dot) fi", "myynti@example.fi"),
    ("pekka.salo at fixture dot example", "pekka.salo@fixture.example"),
    ("info@cablics.com", "info@cablics.com"),
    ("mailto:Sales@Example.FI", "sales@example.fi"),
    ("first.last@sub.domain.co.uk", "first.last@sub.domain.co.uk"),
]


@pytest.mark.parametrize("text", PROSE)
def test_a_sentence_is_never_an_address(text: str) -> None:
    assert norm.normalize_email(text) is None, text


@pytest.mark.parametrize(("text", "expected"), ADDRESSES)
def test_an_obfuscated_address_still_reads(text: str, expected: str) -> None:
    assert norm.normalize_email(text) == expected
