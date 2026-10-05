"""Owner decision 05.10.2026 (ANSWERS_S5): country, department, office_name, address
and fax go to ARGUS only as `field="extra"` + `extra_label`, with a quote."""

from __future__ import annotations

from argus_collector.api_client import contract as api
from argus_collector.scheduler import events, history
from argus_collector.scheduler.tests.test_history import known
from argus_collector.walk import contract as walk

SHA = "0" * 64


def finding(field: str, raw: str, value: str, locator: str = "text") -> walk.FieldFinding:
    return walk.FieldFinding(f"o-{field}", field, raw, value, 10, 10 + len(raw), locator,
                             "caption", "confirmed")


def test_extra_fields_go_as_extra_with_their_label_and_quote() -> None:
    for field, raw, value in [("country", "Finland", "FI"), ("department", "Myynti", "Myynti"),
                              ("office_name", "LEDVANCE Oy", "LEDVANCE Oy"),
                              ("address", "Testikatu 1\n00100 Helsinki",
                               "Testikatu 1, 00100 Helsinki"),
                              ("fax", "09-7422 3301", "+358974223301")]:
        obs = events.observation(finding(field, raw, value), "ev-1", SHA)
        assert (obs.field, obs.extra_label) == ("extra", field)
        assert (obs.quote, obs.raw_value, obs.normalized_value) == (raw, raw, value)
        assert isinstance(obs.locator, api.LocatorTextSpan)


def test_contact_fields_stay_as_they_are() -> None:
    obs = events.observation(finding("phone", "09-7422 3300", "+358974223300"), "ev-1", SHA)
    assert (obs.field, obs.extra_label) == ("phone", None)


def test_fax_from_a_tel_link_points_at_the_link() -> None:
    fax = walk.FieldFinding("o-f", "fax", "+358974223301", "+358974223301", -1, -1,
                            "href:tel", "caption", "confirmed")
    obs = events.observation(fax, "ev-1", SHA)
    assert obs.locator == api.LocatorDom(value='a[href^="tel:"]', text_sha256=SHA)


def test_field_audit_marks_extra_fields() -> None:
    audit = events.field_audit("ev-1", (
        walk.AuditEntry("office[0].phone", ("o1",), "09-7422 3300"),
        walk.AuditEntry("office[0].fax", ("o2",), "09-7422 3301", "fax"),
    ))
    assert [(i.source_field, i.disposition.value, i.reason) for i in audit.items] == [
        ("office[0].phone", "mapped", ""), ("office[0].fax", "extra", "fax"),
    ]


def test_known_extra_fields_come_by_their_label() -> None:
    """The example of docs/ANSWERS_S5.md section 1, plus an office with extra keys."""
    person = known("c-mika", "person", {
        "full_name": "Mika Sormunen", "job_title": "Myynti",
        "phone": ["+358406326632", "+358208351662"], "email": "mika.sormunen@naficon.fi",
    })
    office = known("c-office", "office", {
        "phone": "+358974223300", "country": "FI", "office_name": "ledvance oy",
        "address": "testikatu 1, 00100 helsinki",
    })
    mika, ledvance = history.parse_known([person, office])
    assert mika.keys("phone") == {"+358406326632", "+358208351662"}
    assert set(ledvance.fields) == {"phone", "country", "office_name", "address"}
    index = history.KnownIndex([mika, ledvance])
    assert index.change(ledvance, "address", "Testikatu 1, 00100 Helsinki") == (
        "reconfirmed", None)
    assert index.change(ledvance, "country", "SE") == ("changed", None)
    seen = history.sights({"office:FI:ledvance oy": "office"}, {
        "office:FI:ledvance oy|phone|+358974223300": "p1",
        "office:FI:ledvance oy|country|FI": "c1",
    })
    scope = history.Scope("2 pages", exhausted=True, checked_at="2026-10-05T10:00:00Z")
    checks = history.freshness_checks(index, seen, scope, {})
    office_checks = {
        c.field: c.status.value for c in checks if c.canonical_contact_id == "c-office"
    }
    assert office_checks == {
        "phone": "reconfirmed", "country": "reconfirmed",
        "office_name": "not_seen_in_checked_scope", "address": "not_seen_in_checked_scope",
    }
