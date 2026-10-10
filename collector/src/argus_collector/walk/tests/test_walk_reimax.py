"""Owner 06.10.2026 (Reimax): the page states its address pattern; the rules read 14 people.

The pattern is the company's `email_pattern`, valued as printed so its quote contains
it. Nobody gets an address built from it (0.4.8.11, owner 10.10.2026): a derived
address stands in no line of the page, so ARGUS refuses it (`value_not_in_quote`) -
the server derives those addresses itself. No model is called on the page; the walk
ends at its goal (sales people with a phone).
"""

from __future__ import annotations

from http.server import ThreadingHTTPServer
from pathlib import Path

from argus_collector.discovery import contract as discovery
from argus_collector.models.contract import ModelConfig
from argus_collector.walk import contract
from argus_collector.walk.tests.fake_policy import RankedPolicy
from argus_collector.walk.tests.test_walk_job import RecordingSink, gold, page_order
from argus_collector.walk.tests.test_walk_job import site as site  # noqa: F401 - fixture
from collector.tests.fake_model_server import FakeModelServer
from test_site import server

GOLD = gold("reimax")
PATTERN = GOLD["pattern"]


def run(srv: ThreadingHTTPServer, tmp_path: Path, events: list[contract.WalkEvent]
        ) -> tuple[contract.WalkSummary, RecordingSink]:
    fake = FakeModelServer(RankedPolicy(GOLD["persons"])).start()
    sink = RecordingSink()
    settings = contract.WalkSettings(
        start_url=server.vhost_url(srv, "reimax"), model=ModelConfig(fake.endpoint, "fake"),
        headless=True, profile_dir=tmp_path / "profile", evidence_dir=tmp_path / "evidence",
        db_path=tmp_path / "collector.db", approved_hosts=frozenset({"reimax.localhost"}),
        focus=discovery.make_focus(["FI"], ["fi", "en"]),
        limits=contract.WalkLimits(pages=10, actions=40, seconds=600.0, states=60),
        id_namespace="job-reimax",
    )
    try:
        summary = contract.run_walk(settings, events.append, lambda: False, sink)
    finally:
        fake.stop()
    return summary, sink


def test_the_pattern_is_the_companys_field_and_nobody_gets_a_built_address(
    site: ThreadingHTTPServer, tmp_path: Path,  # noqa: F811
) -> None:
    events: list[contract.WalkEvent] = []
    summary, sink = run(site, tmp_path, events)
    assert summary.end_reason == contract.END_GOAL, summary.gaps
    assert page_order(sink) == ["", "contact/"], "the goal is reached on contact/"
    assert sink.calls == [], "the rules read the page: no model call at all"
    entities = sink.entities()
    for person in GOLD["persons"]:
        fields = {f.field: f for f in entities[person["name"].casefold()].fields}
        assert fields["phone"].value == person["phone"] and fields["phone"].status == "confirmed"
        assert "email" not in fields, f"{person['name']}: no address is built from the pattern"
    patterns = [f for e in entities.values() for f in e.fields if f.field == "email_pattern"]
    assert [(f.value, f.raw) for f in patterns] == [(PATTERN["value"], PATTERN["quote"])]
    text = sink.sources[-1].text
    for found in patterns:
        assert found.value in found.raw, "ARGUS checks that the quote holds the value"
        assert text[found.start:found.end] == found.raw
    values = {f.value for e in entities.values() for f in e.fields if f.field == "email"}
    assert PATTERN["value"] not in values, "the pattern is never an address (RULES K3)"
    goal = [e for e in events if e.step == "goal"]
    assert goal and (goal[-1].people, goal[-1].channels) == (14, 14), "14 people, 14 phones"
    shown = [e.contact for e in events if e.kind == contract.EVENT_CONTACT and e.contact]
    assert len(shown) == 14 and not any(c.email for c in shown)
