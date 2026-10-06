"""Blåkläder through the contract (owner 06.10.2026): «Löydetty: 44» for 22 people.

22 person rows reach ARGUS, none twice although the 7 sales people are shown again on
myynti/, every name as the HTML writes it (the page shows the names in capitals by CSS
`text-transform` only), and the snapshot text the quotes come from has them so too.
"""

from __future__ import annotations

from http.server import ThreadingHTTPServer
from pathlib import Path

from argus_collector.scheduler.tests.stands import System, gold, make_collector, wait_for
from collector.tests.fake_model_server import FakeModelServer
from contract_server import server as contract_server

GOLD = gold("blaklader")
NAMES = {p["name"] for p in GOLD["persons"]}


def test_twenty_two_people_reach_argus_with_their_names_as_written(
    tmp_path: Path, argus: contract_server.ContractServer, site: ThreadingHTTPServer,
    model: FakeModelServer,
) -> None:
    system = System(argus)
    collector = make_collector(tmp_path, argus, model.endpoint)
    collector.deliverer.start()
    collector.start()
    try:
        job_id = system.batch(site, ["blaklader"])["blaklader"]
        wait_for(lambda: system.job(job_id)["state"] in ("completed", "partial", "failed"))
        wait_for(lambda: collector.delivery_view().pending == 0)
        local = collector.queue_view().rows[0]
    finally:
        collector.stop()
        collector.deliverer.stop()
    assert collector.delivery_view().errors == 0, "ARGUS took every event"
    view = system.contacts(job_id)
    people = [c for c in view["contacts"] if c["entity_type"] == "person"]
    names = [o["normalized_value"] for c in people for o in c["observations"]
             if o["field"] == "full_name"]
    assert len(people) == 22 and sorted(set(names)) == sorted(NAMES), names
    assert local.persons == 22, "Jono counts each person once"
    quotes = {o["quote"] for c in people for o in c["observations"] if o["field"] == "full_name"}
    assert not any(q.isupper() for q in quotes), "no name in the capitals of the CSS"
