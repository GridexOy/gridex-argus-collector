"""JSON-LD people (read without the model) and a country tab's panel as a section."""

from __future__ import annotations

from argus_collector.evidence import contract as evidence
from argus_collector.extraction import contract

PEOPLE = ('<script type="application/ld+json">{"@context": "https://schema.org", "@graph": ['
          '{"@type": "Organization", "name": "Beckhoff Automation Oy", "employee": ['
          '{"@type": "Person", "name": "Ari Kinnunen", "jobTitle": "Toimitusjohtaja",'
          ' "telephone": "040 718 2201", "email": "mailto:ari.kinnunen@beckhoff.example"},'
          '{"@type": ["Person"], "name": "Katja Honkanen"}]}]}</script>'
          '<script type="application/ld+json">not json</script>')


def test_jsonld_people_are_cards() -> None:
    people = contract.jsonld_people(PEOPLE)
    assert [(p.name, p.title, p.phone, p.email) for p in people] == [
        ("Ari Kinnunen", "Toimitusjohtaja", "040 718 2201", "ari.kinnunen@beckhoff.example"),
        ("Katja Honkanen", None, None, None),
    ]
    assert contract.jsonld_people("<p>no data</p>") == []


def test_a_selected_country_tab_makes_its_panel_a_section() -> None:
    panel = "Headquarters\nBeckhoff Automation GmbH & Co. KG\nPhone 05246 000-0\n"
    text = evidence.canonical_text("Global presence\nGermany\nBeckhoff Worldwide\n" + panel
                                   + "Imprint\n")
    sections = contract.panel_sections(text, [("Germany", panel), ("Beckhoff Worldwide", "x")])
    assert len(sections) == 1
    section = sections[0]
    assert (section.country, section.heading.quote) == ("DE", "Germany")
    assert text[section.start:section.end].startswith("Headquarters")
    assert text[section.start:section.end].endswith("Phone 05246 000-0")
    channels = contract.extract_channels("", text, "FI", contract.region_resolver(sections, "FI"))
    assert [c.value for c in channels] == ["+4952460000"], "read in the tab's country"
