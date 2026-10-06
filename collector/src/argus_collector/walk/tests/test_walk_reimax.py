"""Owner 06.10.2026 (Reimax): the page states its address pattern; the rules read 14 people.

Every person gets the address the stated pattern gives the name, unconfirmed with
the pattern line as its quote; the pattern is the company's `email_pattern`; no model
is called on the page; the walk ends at its goal (sales people with a phone).
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


def test_every_person_gets_the_stated_pattern_unconfirmed(
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
        email = fields["email"]
        assert email.value == person["email"], person["name"]
        assert (email.status, email.binding) == ("ambiguous", "none"), "ARGUS: inferred"
        assert email.raw == PATTERN["quote"], "the quote is the line that states the pattern"
        text = sink.sources[-1].text
        assert text[email.start:email.end] == email.raw
    patterns = [f for e in entities.values() for f in e.fields if f.field == "email_pattern"]
    assert [(f.value, f.raw) for f in patterns] == [(PATTERN["value"], PATTERN["quote"])]
    values = {f.value for e in entities.values() for f in e.fields if f.field == "email"}
    assert PATTERN["value"] not in values, "the pattern is never an address (RULES K3)"
    goal = [e for e in events if e.step == "goal"]
    assert goal and (goal[-1].people, goal[-1].channels) == (14, 14), "14 people, 14 phones"
    shown = [e.contact for e in events if e.kind == contract.EVENT_CONTACT and e.contact]
    assert len(shown) == 14 and all(c.email and c.email.locator == "pattern" for c in shown)
