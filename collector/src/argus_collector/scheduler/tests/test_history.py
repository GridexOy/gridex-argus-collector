"""Known contacts: any value shape, change kinds, run sights, freshness statuses."""

from __future__ import annotations

from argus_collector.api_client import contract as api
from argus_collector.scheduler import history


def known(contact_id: str, kind: str, fields: dict[str, object]) -> api.KnownContact:
    return api.KnownContact(
        canonical_contact_id=contact_id, entity_type=api.KnownContactEntityType(kind),
        fields=fields, last_seen_at=None, channel_status=api.ChannelStatus("published_direct"),
    )


ANNA = known("c-anna", "person", {
    "full_name": [{"value": "Anna Virtanen", "observation_id": "o-name"}],
    "job_title": "Sales Director",
    "phone": ["+358401234567"],
    "email": {"value": "anna.virtanen@fixture.example", "observation_id": "o-mail"},
})
DESK = known("c-desk", "organization_channel", {"email": [{"value": "info@fixture.example"}]})


def test_every_value_shape_is_read() -> None:
    anna = history.parse_known([ANNA])[0]
    assert anna.keys("job_title") == {"sales director"}
    assert anna.keys("phone") == {"+358401234567"}
    assert anna.fields["email"][0].observation_id == "o-mail"


def test_change_kinds_against_known_values() -> None:
    index = history.KnownIndex(history.parse_known([ANNA, DESK]))
    anna = index.match("person", "anna virtanen", {})
    assert anna is not None and anna.contact_id == "c-anna"
    assert index.change(anna, "email", "Anna.Virtanen@fixture.example") == ("reconfirmed", None)
    assert index.change(anna, "email", "anna@new.example") == ("changed", "o-mail")
    assert index.change(anna, "department", "Myynti") == ("new", None)
    assert index.change(None, "phone", "+358401234567") == ("new", None)
    desk = index.match("organization_channel", "organization_channel:email|x",
                       {"email": {"info@fixture.example"}})
    assert desk is not None and desk.contact_id == "c-desk"


def test_sights_take_the_longest_entity_key() -> None:
    types = {"anna virtanen": "person", "anna virtanen|a2@x.example": "person"}
    obs = {"anna virtanen|phone|+358401234567": "o1",
           "anna virtanen|a2@x.example|email|a2@x.example": "o2"}
    seen = history.sights(types, obs)
    assert seen["anna virtanen"].values == {"phone": {"+358401234567"}}
    assert seen["anna virtanen|a2@x.example"].values == {"email": {"a2@x.example"}}


def test_freshness_statuses() -> None:
    index = history.KnownIndex(history.parse_known([ANNA, DESK]))
    seen = history.sights({"anna virtanen": "person"}, {
        "anna virtanen|full_name|Anna Virtanen": "n1",
        "anna virtanen|job_title|Head of Sales": "t1",
        "anna virtanen|phone|+358401234567": "p1",
    })
    scope = history.Scope("5 pages on fixture", exhausted=True, checked_at="2026-10-05T10:00:00")
    checks = history.freshness_checks(index, seen, scope, {"p1": "ev-1"})
    by = {(c.canonical_contact_id, c.field): c for c in checks}
    assert by[("c-anna", "full_name")].status.value == "reconfirmed"
    assert by[("c-anna", "job_title")].status.value == "changed"
    assert by[("c-anna", "phone")].evidence_ids == ["ev-1"]
    assert by[("c-anna", "email")].status.value == "not_seen_in_checked_scope"
    assert by[("c-desk", "email")].status.value == "not_seen_in_checked_scope"
    partial = history.Scope("2 pages", exhausted=False, checked_at="2026-10-05T10:00:00")
    later = history.freshness_checks(index, {}, partial, {})
    assert {c.status.value for c in later} == {"not_checked"}
