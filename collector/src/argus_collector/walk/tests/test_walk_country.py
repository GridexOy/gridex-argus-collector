"""Owner decisions 05.10.2026 on real fixture sites (job mode, fake model).

Ledvance: on the international contact page only Finland is opened; its
office (name, address, switchboard, email, country; no fax) is one entity,
the local version /fi-fi/ is followed through a bot check that clears by
itself, and its people are taken; no other country is walked.
Malux: the seed is the Finnish version, every department tab is opened
(sales first), the Swedish sister site comes after and its people carry SE.
"""

from __future__ import annotations

from dataclasses import replace
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


def run(srv: ThreadingHTTPServer, label: str, path: str, hosts: set[str], tmp_path: Path,
        local: bool = False) -> tuple[contract.WalkSummary, RecordingSink]:
    persons = [p for name in ("ledvance", "malux") for p in gold(name)["persons"]]
    fake = FakeModelServer(RankedPolicy(persons)).start()
    sink = RecordingSink()
    focus = discovery.make_focus(["FI"], ["fi", "en"])
    assert focus is not None
    settings = contract.WalkSettings(
        start_url=server.vhost_url(srv, label) + path,
        model=ModelConfig(fake.endpoint, "fake-instruct"), headless=True,
        profile_dir=tmp_path / "profile", evidence_dir=tmp_path / "evidence",
        db_path=tmp_path / "collector.db", approved_hosts=frozenset(hosts),
        focus=replace(focus, local_seed=local),
        limits=contract.WalkLimits(pages=20, actions=60, seconds=900.0, states=120),
        id_namespace="job-" + label,
    )
    try:
        summary = contract.run_walk(settings, lambda e: None, lambda: False, sink)
    finally:
        fake.stop()
    return summary, sink


def fields(entity: contract.EntityFinding) -> dict[str, str]:
    return {f.field: f.value for f in entity.fields}


def test_ledvance_finland_office_and_local_people(site: ThreadingHTTPServer,  # noqa: F811
                                                  tmp_path: Path) -> None:
    summary, sink = run(site, "ledvance", "", {"ledvance.localhost"}, tmp_path)
    assert summary.end_reason == contract.END_FINISHED, summary.gaps
    offices = [e for e in sink.entities().values() if e.entity_type == "office"]
    finland = [fields(e) for e in offices if fields(e).get("country") == "FI"]
    assert finland and finland[0]["phone"] == "+358974223300"
    assert finland[0]["email"] == "asiakaspalvelu@ledvance.com"
    assert finland[0]["office_name"] == "LEDVANCE Oy"
    assert "00100 Helsinki" in finland[0]["address"]
    values = {f.value for e in sink.entities().values() for f in e.fields}
    assert "+358974223301" not in values, "the fax is not taken"
    others = gold("ledvance")["excluded"][1]["offices"]
    leaked = {v for o in others for v in (o["email"], o["phone"])} & values
    assert not leaked, "closed country sections are not read"
    assert {fields(e).get("country") for e in offices} == {"FI"}, "no other country opened"
    order = page_order(sink)
    assert not [p for p in order if p.startswith(("de-de", "sv-se", "fr-fr"))], order
    names = {e.entity_key for e in sink.entities().values() if e.entity_type == "person"}
    for person in gold("ledvance")["persons"]:
        assert person["name"].casefold() in names, person["name"]


def test_malux_every_tab_finnish_first_then_sweden(site: ThreadingHTTPServer,  # noqa: F811
                                                   tmp_path: Path) -> None:
    hosts = {"malux.localhost", "malux-se.localhost"}
    summary, sink = run(site, "malux", "fi/", hosts, tmp_path, local=True)
    assert summary.end_reason == contract.END_FINISHED, summary.gaps
    people = [e for f in sink.findings for e in f.entities if e.entity_type == "person"]
    first_seen: list[str] = []
    for entity in people:
        if entity.entity_key not in first_seen:
            first_seen.append(entity.entity_key)
    by_name: dict[str, dict[str, str]] = {e.entity_key: {} for e in people}
    for entity in people:
        by_name[entity.entity_key].update(fields(entity))
    expected = gold("malux")["persons"]
    for person in expected:
        got = by_name[person["name"].casefold()]
        assert got["phone"] == person["phone"], person["name"]
        assert got.get("country") == person["country"], person["name"]
        if person.get("department"):
            assert got.get("department") == person["department"], person["name"]
    swedes = [p["name"].casefold() for p in expected if p["country"] == "SE"]
    finns = [p["name"].casefold() for p in expected if p["country"] == "FI"]
    assert max(first_seen.index(n) for n in finns) < min(first_seen.index(n) for n in swedes)
    joakim = by_name["joakim flakholm"]
    assert joakim["job_title"] == "Maajohtaja" and joakim["department"] == "Johto"
    company = [fields(e) for f in sink.findings for e in f.entities if e.entity_type != "person"]
    assert all(c.get("country") in ("FI", "SE") for c in company if "phone" in c or "email" in c)
    kinds = {e.entity_type for f in sink.findings for e in f.entities}
    assert "unassigned_channel" not in kinds, "an email of a closed tab waits for its card"
