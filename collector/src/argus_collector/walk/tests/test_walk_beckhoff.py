"""Owner 05.10.2026 (Beckhoff, MAIN-PC): Global presence -> Beckhoff Worldwide -> Finland
-> /fi-fi/ instead of Global presence -> Germany; routing rules -> 7b -> 14b."""

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

GOLD = gold("beckhoff")


def run(srv: ThreadingHTTPServer, tmp_path: Path) -> tuple[contract.WalkSummary, RecordingSink]:
    fake = FakeModelServer(RankedPolicy(GOLD["persons"])).start()
    sink = RecordingSink()
    focus = discovery.make_focus(["FI"], ["fi", "en"])
    assert focus is not None
    settings = contract.WalkSettings(
        start_url=server.vhost_url(srv, "beckhoff") + "en-en/",
        model=ModelConfig(fake.endpoint, "qwen2.5:14b"),
        navigation=ModelConfig(fake.endpoint, "qwen2.5:7b"), headless=True,
        profile_dir=tmp_path / "profile", evidence_dir=tmp_path / "evidence",
        db_path=tmp_path / "collector.db", approved_hosts=frozenset({"beckhoff.localhost"}),
        focus=replace(focus, local_seed=False),
        limits=contract.WalkLimits(pages=20, actions=60, seconds=900.0, states=120),
        id_namespace="job-beckhoff",
    )
    try:
        summary = contract.run_walk(settings, lambda e: None, lambda: False, sink)
    finally:
        fake.stop()
    return summary, sink


def fields(entity: contract.EntityFinding) -> dict[str, str]:
    return {f.field: f.value for f in entity.fields}


def test_beckhoff_worldwide_finland_then_the_finnish_people(
    site: ThreadingHTTPServer, tmp_path: Path,  # noqa: F811
) -> None:
    summary, sink = run(site, tmp_path)
    assert summary.end_reason == contract.END_FINISHED, summary.gaps
    order = page_order(sink)
    assert order[:4] == ["en-en/", "en-en/company/global-presence/", "fi-fi/",
                         "fi-fi/yhteystiedot/"], order
    assert not [p for p in order if p.startswith("de-de")], "Germany is never walked"
    after = order[order.index("fi-fi/"):]
    assert all(p.startswith("fi-fi") for p in after), "no way back to /en-en/"
    entities = sink.entities().values()
    offices = {fields(e).get("country"): fields(e) for e in entities if e.entity_type == "office"}
    office = GOLD["company"]["offices"][0]
    finland = offices["FI"]
    assert (finland["phone"], finland["email"], finland["fax"]) == (
        office["phone"], office["email"], office["fax"])
    assert finland["office_name"] == office["name"] and "01510 Vantaa" in finland["address"]
    german = {f.value for e in entities if e.entity_type == "office"
              and fields(e).get("country") == "DE" for f in e.fields if f.field == "phone"}
    assert "+4952460000" in german, "the open Germany tab is DE (Muut maat)"
    names = {e.entity_key for e in entities if e.entity_type == "person"}
    assert {p["name"].casefold() for p in GOLD["persons"]} <= names


def test_beckhoff_routing_rules_first_7b_steps_14b_cards_once(
    site: ThreadingHTTPServer, tmp_path: Path,  # noqa: F811
) -> None:
    _, sink = run(site, tmp_path)
    calls = [(c.purpose.split(":", 1)[0], c.model) for c in sink.calls]
    cards = [model for purpose, model in calls if purpose == "walk.cards"]
    steps = [model for purpose, model in calls if purpose == "walk.action"]
    assert cards == ["qwen2.5:14b"], "only fi-fi/yhteystiedot needs the card model"
    assert steps and set(steps) == {"qwen2.5:7b"} and len(steps) <= 3
