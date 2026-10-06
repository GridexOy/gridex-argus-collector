"""K7 through the contract (owner 06.10.2026, Elkris/Reimax): the event site's page is a
source of the job, nobody of it reaches ARGUS as the company's person or channel."""

from __future__ import annotations

from http.server import ThreadingHTTPServer
from pathlib import Path

from argus_collector.scheduler.tests.stands import System, gold, make_collector, wait_for
from collector.tests.fake_model_server import FakeModelServer
from contract_server import server as contract_server

GOLD = gold("elkris")


def test_people_of_the_event_site_never_reach_argus(
    tmp_path: Path, argus: contract_server.ContractServer, site: ThreadingHTTPServer,
    model: FakeModelServer,
) -> None:
    system = System(argus)
    collector = make_collector(tmp_path, argus, model.endpoint)
    collector.deliverer.start()
    collector.start()
    try:
        job_id = system.batch(site, ["elkris"])["elkris"]
        wait_for(lambda: system.job(job_id)["state"] in ("completed", "partial", "failed"))
        wait_for(lambda: collector.delivery_view().pending == 0)
    finally:
        collector.stop()
        collector.deliverer.stop()
    view = system.contacts(job_id)
    assert any(GOLD["foreign_host"] in s["url"] for s in view["sources"]), "a source"
    assert [c for c in view["contacts"] if c["entity_type"] == "person"] == []
    values = {o["normalized_value"] for c in view["contacts"] for o in c["observations"]}
    for person in GOLD["foreign_persons"]:
        assert not {person["phone"], person["email"]} & values, person["name"]
    assert GOLD["company"]["email"] in values, "the company's own channel is there"
