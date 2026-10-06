"""K7 (owner 06.10.2026, Elkris/Reimax): a professor of an event site came in as a contact.

A person and a channel come only from pages of the company's domain (or its subdomains);
the event page on another approved host is stored as a source - it confirms the
participation - and nobody is read from it. Without the rule the same page gives both.
"""

from __future__ import annotations

from http.server import ThreadingHTTPServer
from pathlib import Path

from argus_collector.discovery import contract as discovery
from argus_collector.models.contract import ModelConfig
from argus_collector.walk import contract
from argus_collector.walk.tests.fake_policy import RankedPolicy
from argus_collector.walk.tests.test_walk_job import RecordingSink, gold
from argus_collector.walk.tests.test_walk_job import site as site  # noqa: F401 - fixture
from collector.tests.fake_model_server import FakeModelServer
from test_site import server

GOLD = gold("elkris")
FOREIGN = GOLD["foreign_host"]


def run(srv: ThreadingHTTPServer, tmp_path: Path, domains: frozenset[str] | None,
        events: list[contract.WalkEvent]) -> RecordingSink:
    fake = FakeModelServer(RankedPolicy(GOLD["foreign_persons"])).start()
    sink = RecordingSink()
    settings = contract.WalkSettings(
        start_url=server.vhost_url(srv, "elkris"), model=ModelConfig(fake.endpoint, "fake"),
        headless=True, profile_dir=tmp_path / "profile", evidence_dir=tmp_path / "evidence",
        db_path=tmp_path / "collector.db", approved_hosts=frozenset({GOLD["host"], FOREIGN}),
        focus=discovery.make_focus(["FI"], ["fi", "en"]),
        limits=contract.WalkLimits(pages=8, actions=30, seconds=300.0, states=40),
        id_namespace="job-elkris", company_domains=domains,
    )
    try:
        contract.run_walk(settings, events.append, lambda: False, sink)
    finally:
        fake.stop()
    return sink


def values(sink: RecordingSink) -> set[str]:
    return {f.value for e in sink.entities().values() for f in e.fields}


def test_people_of_another_domain_are_not_read(
    site: ThreadingHTTPServer, tmp_path: Path,  # noqa: F811
) -> None:
    events: list[contract.WalkEvent] = []
    sink = run(site, tmp_path, frozenset({"elkris.localhost"}), events)
    stored = [s.url for s in sink.sources]
    assert any(FOREIGN in url for url in stored), "the event page is kept as a source"
    people = [e for e in sink.entities().values() if e.entity_type == "person"]
    assert people == [], [e.entity_key for e in people]
    found = values(sink)
    for person in GOLD["foreign_persons"]:
        assert not {person["phone"], person["email"]} & found, person["name"]
    assert "info@industryx.example" not in found, "no channel of the event site either"
    assert GOLD["company"]["email"] in found, "the company's own channels still are"
    foreign = [e for e in events if e.kind == "step" and e.step == "foreign"]
    assert [e.detail for e in foreign] == [FOREIGN], "told once per host"
    shown = [e for e in events if e.kind == contract.EVENT_CONTACT]
    assert shown == []


def test_without_the_rule_the_same_page_gives_both(
    site: ThreadingHTTPServer, tmp_path: Path,  # noqa: F811
) -> None:
    """The fixture is real: the page's two cards are read when no domain is set."""
    sink = run(site, tmp_path, None, [])
    names = {e.entity_key for e in sink.entities().values() if e.entity_type == "person"}
    assert names == {p["name"].casefold() for p in GOLD["foreign_persons"]}
