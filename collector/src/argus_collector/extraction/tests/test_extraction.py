"""Extraction: deterministic channels and the verbatim check of model cards."""

from __future__ import annotations

from argus_collector.evidence.contract import canonical_text
from argus_collector.extraction import contract
from argus_collector.extraction.contract import PersonCard

HTML = """<html><body>
<script type="application/ld+json">{"@type":"Organization","telephone":"+358 20 123 4560",
 "contactPoint":{"email":"Info@Fixture.Example"}}</script>
<ul><li class="person"><span>Anna Virtanen</span> <span>Sales Director</span>
<a href="mailto:anna.virtanen@fixture.example">anna.virtanen@fixture.example</a>
<a href="tel:+358401234567">040 123 4567</a></li>
<li><span>Pekka Salo</span> <span>Buyer</span> pekka.salo (at) fixture.example</li>
<li><span>Sari</span> <a href="/cdn-cgi/l/email-protection" data-cfemail="5a292b2831"
 class="__cf_email__">[email]</a></li>
</ul><p>Founded 1987. Order no. 12345678.</p></body></html>"""
TEXT = canonical_text(
    "Anna Virtanen Sales Director\nanna.virtanen@fixture.example\n040 123 4567\n"
    "Pekka Salo Buyer pekka.salo (at) fixture.example\nSari [email]\n"
    "Founded 1987. Order no. 12345678."
)


def test_extract_channels_from_hrefs_jsonld_text_and_cfemail() -> None:
    channels = contract.extract_channels(HTML, TEXT)
    by_value = {c.value: c for c in channels}
    anna_phone = by_value["+358401234567"]
    assert anna_phone.locator == "href:tel" and anna_phone.raw == "040 123 4567"
    assert (
        anna_phone.span is not None
        and TEXT[anna_phone.span.start : anna_phone.span.end] == "040 123 4567"
    )
    assert by_value["anna.virtanen@fixture.example"].locator == "href:mailto"
    assert by_value["+358201234560"].locator.startswith("jsonld:0/telephone")
    assert by_value["info@fixture.example"].locator == "jsonld:0/contactPoint/email"
    pekka = by_value["pekka.salo@fixture.example"]
    assert pekka.locator == "text" and pekka.raw == "pekka.salo (at) fixture.example"
    assert "sqr" not in by_value  # cfemail decoding requires a real key/payload
    assert not any(c.value.endswith("12345678") for c in channels)
    assert len(channels) == len(by_value)


def test_cfemail_channel() -> None:
    address, key = "sari@fixture.example", 0x3C
    encoded = f"{key:02x}" + "".join(f"{ord(c) ^ key:02x}" for c in address)
    html = f'<a data-cfemail="{encoded}">[email]</a>'
    channels = contract.extract_channels(html, "x")
    assert channels == [contract.Channel("email", address, encoded, "cfemail", None)]


def test_has_contact_signals() -> None:
    assert contract.has_contact_signals("Ota yhteyttä: yhteystiedot", [])
    assert not contract.has_contact_signals("Products and prices", [])
    channels = contract.extract_channels(HTML, TEXT)
    assert contract.has_contact_signals("anything", channels)


def test_verify_card_keeps_only_verbatim_fields() -> None:
    channels = contract.extract_channels(HTML, TEXT)
    card = PersonCard(
        "Anna  Virtanen", "Sales Director", "+358401234567", "ANNA.VIRTANEN@fixture.example"
    )
    contact = contract.verify_card(card, TEXT, channels)
    assert contact is not None
    assert contact.name.value == "Anna Virtanen" and contact.name.quote == "Anna Virtanen"
    assert TEXT[contact.name.start : contact.name.end] == "Anna Virtanen"
    assert contact.title is not None and contact.title.value == "Sales Director"
    assert contact.phone is not None and contact.phone.value == "+358401234567"
    assert contact.phone.locator == "href:tel" and contact.phone.quote == "040 123 4567"
    assert contact.email is not None and contact.email.locator == "href:mailto"


def test_verify_card_drops_invented_values() -> None:
    channels = contract.extract_channels(HTML, TEXT)
    card = PersonCard("Anna Virtanen", "Chief Executive", "050 999 9999", "anna@elsewhere.example")
    contact = contract.verify_card(card, TEXT, channels)
    assert contact is not None
    assert contact.title is None and contact.phone is None and contact.email is None
    assert contract.verify_card(PersonCard("Ghost Person", "CEO"), TEXT, channels) is None
    assert contract.verify_card(PersonCard("040 123 4567"), TEXT, channels) is None


def test_verify_card_obfuscated_email_quote_from_text() -> None:
    channels = contract.extract_channels(HTML, TEXT)
    contact = contract.verify_card(
        PersonCard("Pekka Salo", "Buyer", None, "pekka.salo (at) fixture.example"), TEXT, channels
    )
    assert contact is not None and contact.email is not None
    assert contact.email.value == "pekka.salo@fixture.example"
    assert (
        contact.email.quote == "pekka.salo (at) fixture.example" and contact.email.locator == "text"
    )


def test_card_from_json() -> None:
    assert contract.card_from_json({"name": " Anna ", "title": "", "phone": 123}) == PersonCard(
        "Anna", None, "123", None
    )
    assert contract.card_from_json({"title": "x"}) is None
    assert contract.card_from_json("Anna") is None
