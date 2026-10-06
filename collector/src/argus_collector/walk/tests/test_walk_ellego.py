"""Owner 05.10.2026 (Ellego, MAIN-PC): the walk went in circles on contact/ and read nobody.

Now every card is read on contact/ by the rules before any click or navigation (9000
characters of mega menu come first), no filter button is pressed, no page is entered
twice, no model is called, and the walk ends at its goal there.
"""

from __future__ import annotations

from collections import Counter
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

GOLD = gold("ellego")


def test_forty_people_on_contact_without_a_repeat(
    site: ThreadingHTTPServer, tmp_path: Path,  # noqa: F811
) -> None:
    fake = FakeModelServer(RankedPolicy(GOLD["persons"])).start()
    sink, events = RecordingSink(), list[contract.WalkEvent]()
    settings = contract.WalkSettings(
        start_url=server.vhost_url(site, "ellego"), model=ModelConfig(fake.endpoint, "fake"),
        headless=True, profile_dir=tmp_path / "profile", evidence_dir=tmp_path / "evidence",
        db_path=tmp_path / "collector.db", approved_hosts=frozenset({"ellego.localhost"}),
        focus=discovery.make_focus(["FI"], ["fi", "en"]),
        limits=contract.WalkLimits(pages=15, actions=60, seconds=600.0, states=120),
        id_namespace="job-ellego",
    )
    try:
        summary = contract.run_walk(settings, events.append, lambda: False, sink)
    finally:
        fake.stop()
    assert summary.end_reason == contract.END_GOAL, summary.gaps
    assert page_order(sink) == ["", "contact/"]
    names = {e.entity_key for e in sink.entities().values() if e.entity_type == "person"}
    assert names == {p["name"].casefold() for p in GOLD["persons"]}, "all 40 cards"
    steps = Counter((e.step, e.detail) for e in events if e.kind == "step")
    assert not [s for s in steps if s[0] in ("click", "loop")], steps
    assert all(n == 1 for (step, _), n in steps.items() if step == "navigate"), steps
    states = Counter(s.state_key for s in sink.sources)
    assert set(states.values()) == {1}, "no page state is entered twice"
    assert sink.calls == [], "no model call: the rules read the cards and walk"
