"""Owner 06.10.2026 (Carlo Gavazzi went to /en-br/): the exhibition country's version first.

The seed lands on the Brazilian version; the site has locale paths, `/fi/` answers
404 and `/en-fi/` is the Finnish version: the walk goes there before reading anything,
the panel says `Maa: FI (vaihdettu en-br → en-fi)`, nobody of the Brazilian office is
read and the Finnish people have the country FI.
"""

from __future__ import annotations

from http.server import ThreadingHTTPServer
from pathlib import Path

from argus_collector.discovery import contract as discovery
from argus_collector.extraction.contract import VerifiedField
from argus_collector.models.contract import ModelConfig
from argus_collector.walk import context, contract
from argus_collector.walk.tests.fake_policy import RankedPolicy
from argus_collector.walk.tests.test_walk_job import RecordingSink, gold
from argus_collector.walk.tests.test_walk_job import site as site  # noqa: F401 - fixture
from collector.tests.fake_model_server import FakeModelServer
from test_site import server

GOLD = gold("gavazzi")


def test_the_walk_goes_to_the_finnish_version_first(
    site: ThreadingHTTPServer, tmp_path: Path,  # noqa: F811
) -> None:
    fake = FakeModelServer(RankedPolicy(GOLD["persons"])).start()
    sink, events = RecordingSink(), list[contract.WalkEvent]()
    settings = contract.WalkSettings(
        start_url=server.vhost_url(site, "gavazzi") + GOLD["seed"],
        model=ModelConfig(fake.endpoint, "fake"), headless=True,
        profile_dir=tmp_path / "profile", evidence_dir=tmp_path / "evidence",
        db_path=tmp_path / "collector.db", approved_hosts=frozenset({GOLD["host"]}),
        focus=discovery.make_focus(["FI"], ["fi", "en"]),
        limits=contract.WalkLimits(pages=8, actions=30, seconds=300.0, states=40),
        id_namespace="job-gavazzi",
    )
    try:
        contract.run_walk(settings, events.append, lambda: False, sink)
    finally:
        fake.stop()
    country = [e for e in events if e.kind == "step" and e.step == "country"]
    assert [e.detail for e in country] == ["FI|en-br|en-fi|local"]
    assert not any("/en-br/" in s.url for s in sink.sources), "nothing read on /en-br/"
    people = {e.entity_key: e for e in sink.entities().values() if e.entity_type == "person"}
    assert set(people) == {p["name"].casefold() for p in GOLD["persons"]}
    for entity in people.values():
        fields = {f.field: f.value for f in entity.fields}
        assert fields.get("country") == "FI", entity.entity_key


def test_a_person_country_comes_from_the_phone_before_the_page_language() -> None:
    phone = VerifiedField("+358975620101", "+358 9 7562 0101", 40, 56, "text")
    page = context.PageContext(lang="en-BR")
    found = context.country_field(page, 10, phone)
    assert found is not None and (found.value, found.quote) == ("FI", "+358 9 7562 0101")
    bare = context.country_field(page, 10, None)
    assert bare is not None and bare.value == "BR", "no phone: the page's region"
