"""Country sections, phones in the section's country, fax left out, office lines."""

from __future__ import annotations

from argus_collector.extraction import contract as extraction

TEXT = """Contact LEDVANCE worldwide
Austria
Belgium
Finland
LEDVANCE Oy
Testikatu 1
00100 Helsinki
Phone 09-7422 3300
Fax 09-7422 3301
asiakaspalvelu@ledvance.com
www.ledvance.com/fi-fi
Germany
LEDVANCE GmbH
Parkring 29
85748 Garching
Telefon 089 1234 5670
Sweden"""
HTML = '<a href="mailto:asiakaspalvelu@ledvance.com">asiakaspalvelu@ledvance.com</a>'


def test_sections_and_section_regions() -> None:
    sections = extraction.country_sections(TEXT)
    assert [(s.country, s.heading.quote) for s in sections] == [("FI", "Finland"),
                                                              ("DE", "Germany")]
    region = extraction.region_resolver(sections, "FI")
    channels = extraction.extract_channels(HTML, TEXT, "FI", region)
    phones = sorted(c.value for c in channels if c.kind == "phone")
    assert phones == ["+358974223300", "+498912345670"], "the fax 3301 is not a phone"


def test_office_lines() -> None:
    finland, germany = extraction.country_sections(TEXT)
    office = extraction.office_lines(TEXT, finland)
    assert office.name is not None and office.name.quote == "LEDVANCE Oy"
    assert office.address is not None and office.address.quote == "Testikatu 1\n00100 Helsinki"
    assert TEXT[office.address.start : office.address.end] == office.address.quote
    german = extraction.office_lines(TEXT, germany)
    assert german.address is not None and german.address.quote == "Parkring 29\n85748 Garching"


def test_no_sections_without_a_country_list() -> None:
    menu = "Deutsch\nEnglish\nSuomi\nKontakt\nTel. 0711 123 4500"
    assert extraction.country_sections(menu) == []
    channels = extraction.extract_channels("", menu, "DE")
    assert [c.value for c in channels] == ["+497111234500"]


def test_fax_label_on_the_line_or_above() -> None:
    text = "Puh. 09 123 4567, faksi 09 123 4568\nTelefax\n09 123 4569\nVaihde 09 123 4500"
    values = sorted(c.value for c in extraction.extract_channels("", text, "FI"))
    assert values == ["+35891234500", "+35891234567"]
