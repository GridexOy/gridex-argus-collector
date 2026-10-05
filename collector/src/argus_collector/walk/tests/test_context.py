"""Department and country of an entity: evidence-backed or not sent at all."""

from __future__ import annotations

from argus_collector.extraction import contract as extraction
from argus_collector.walk import context as ctx

TEXT = "Yhteystiedot\nHallinto\nJohto\nJoakim Flakholm\nMaajohtaja\n040 123 4567"


def contact(name: str, title: str | None = None) -> extraction.Contact:
    start = TEXT.find(name)
    vf = extraction.VerifiedField(name, name, start, start + len(name), "text")
    tstart = TEXT.find(title) if title else -1
    tf = (extraction.VerifiedField(title, title, tstart, tstart + len(title), "text")
          if title else None)
    return extraction.Contact(vf, tf, None, None)


def test_department_is_quoted_before_the_name() -> None:
    found = ctx.department_field(TEXT, "Johto", contact("Joakim Flakholm", "Maajohtaja"))
    assert found is not None and found.value == "Johto"
    assert TEXT[found.start : found.end] == "Johto" and found.start < TEXT.find("Joakim")


def test_generic_country_and_company_headings_are_not_departments() -> None:
    person = contact("Joakim Flakholm", "Maajohtaja")
    for heading in ("Yhteystiedot", "Ota yhteyttä", "Finland", "Malux Finland Oy", "Maajohtaja",
                    "", "x" * 61):
        assert ctx.department_field(TEXT + "\n" + heading, heading, person) is None, heading


def test_country_from_lang_region_only() -> None:
    swedish = ctx.country_field(ctx.PageContext((), "sv-SE"), 10)
    assert swedish is not None and (swedish.value, swedish.quote) == ("SE", "sv-SE")
    assert swedish.locator == ctx.LOCATOR_LANG
    assert ctx.country_field(ctx.PageContext((), "fi"), 10) is None, "a language is no country"
    assert ctx.country_field(ctx.PageContext((), ""), 10) is None
