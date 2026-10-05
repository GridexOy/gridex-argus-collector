"""Pair A4: a re-run reconfirms what is still there and reports who is gone."""

from __future__ import annotations

from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

from argus_collector.scheduler import contract as scheduler
from argus_collector.scheduler.tests.stands import System, gold, make_collector, wait_for
from collector.tests.fake_model_server import FakeModelServer
from contract_server import server as contract_server
from test_site import server

PERSONS = {p["name"] for p in gold("fixture_oy")["persons"]}
DEPARTED = "Pekka Salo"


def run(collector: scheduler.Collector, system: System, job_id: str) -> dict[str, Any]:
    wait_for(lambda: system.job(job_id)["state"] in ("completed", "partial", "failed"))
    wait_for(lambda: collector.delivery_view().pending == 0)
    return system.job(job_id)


def checks_of(system: System, job_id: str) -> list[dict[str, Any]]:
    return [dict(c) for c in system.contacts(job_id)["freshness"]]


def person_rows(system: System) -> dict[str, dict[str, Any]]:
    rows = system.company("fixture_oy")["contacts"]
    out = {}
    for contact in rows:
        names = [o["normalized_value"] for o in contact["observations"]
                 if o["field"] == "full_name"]
        if contact["entity_type"] == "person" and names:
            out[names[0]] = contact
    return out


def test_rerun_reconfirms_and_a_departed_person_is_not_seen(
    tmp_path: Path, argus: contract_server.ContractServer, site: ThreadingHTTPServer,
    model: FakeModelServer,
) -> None:
    system = System(argus)
    collector = make_collector(tmp_path, argus, model.endpoint)
    collector.deliverer.start()
    collector.start()
    first = system.batch(site, ["fixture_oy"])["fixture_oy"]
    run(collector, system, first)
    before = person_rows(system)
    assert set(before) == PERSONS
    second = system.batch(site, ["fixture_oy"], rerun="A4 test: same site")["fixture_oy"]
    run(collector, system, second)
    checks = checks_of(system, second)
    assert checks and {c["status"] for c in checks} == {"reconfirmed"}, checks
    assert set(person_rows(system)) == PERSONS, "no new person rows"
    departed = server.start(port=0, variant="departed")
    try:
        third_site = departed
        third = system.batch(third_site, ["fixture_oy"], rerun="A4 test: one left")["fixture_oy"]
        status = run(collector, system, third)
    finally:
        collector.stop()
        collector.deliverer.stop()
        departed.shutdown()
        departed.server_close()
    pekka = person_rows(system)[DEPARTED]
    assert pekka["not_seen"] is not None, "the person stays, marked not seen"
    gone = [c for c in checks_of(system, third) if c["canonical_contact_id"]
            == pekka["canonical_contact_id"]]
    assert gone and {c["status"] for c in gone} == {"not_seen_in_checked_scope"}
    assert status["state"] == "completed"
