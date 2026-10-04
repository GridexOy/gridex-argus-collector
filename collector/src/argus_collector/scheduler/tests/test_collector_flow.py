"""Pair A2 end to end: claim -> walk by seed in approved hosts -> outbox -> ARGUS.

The contract server validates every request against the OpenAPI schema and
checks quotes against the uploaded snapshots, approved hosts and field audits.
"""

from __future__ import annotations

from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

from argus_collector.scheduler.tests.stands import System, gold, make_collector, wait_for
from collector.tests.fake_model_server import FakeModelServer
from contract_server import server as contract_server

IDS = ["fixture_oy", "nordtec", "vogel", "katsa"]


def run_batch(
    tmp: Path, argus: contract_server.ContractServer, site: ThreadingHTTPServer,
    model: FakeModelServer,
) -> tuple[System, dict[str, str]]:
    system = System(argus)
    jobs = system.batch(site, IDS)
    collector = make_collector(tmp, argus, model.endpoint)
    collector.deliverer.start()
    collector.start()
    try:
        done = ("completed", "partial", "failed", "cancelled")
        wait_for(lambda: all(system.job(j)["state"] in done for j in jobs.values()))
        wait_for(lambda: collector.delivery_view().pending == 0)
    finally:
        collector.stop()
        collector.deliverer.stop()
    return system, jobs


def persons(view: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out = {}
    for contact in view["contacts"]:
        if contact["entity_type"] == "person":
            fields = {o["field"]: o for o in contact["observations"]}
            out[fields["full_name"]["normalized_value"]] = fields
    return out


def test_batch_reaches_argus_with_evidence_and_statuses(
    tmp_path: Path, argus: contract_server.ContractServer, site: ThreadingHTTPServer,
    model: FakeModelServer,
) -> None:
    system, jobs = run_batch(tmp_path, argus, site, model)
    for company_id, job_id in jobs.items():
        assert system.contacts(job_id)["rejected"] == [], company_id
    oy = system.contacts(jobs["fixture_oy"])
    found = persons(oy)
    for person in gold("fixture_oy")["persons"]:
        fields = found[person["name"]]
        assert fields["email"]["normalized_value"] == person["email"]
        assert fields["phone"]["normalized_value"] == person["phone"]
        assert fields["phone"]["channel_status"] == "published_direct", person["name"]
        assert fields["phone"]["binding"] == "card" and fields["phone"]["evidence_id"]
    assert len(found) == len(gold("fixture_oy")["persons"]), "no duplicate persons"
    footer = [c for c in oy["contacts"] if c["entity_type"] == "organization_channel"]
    values = {o["normalized_value"]: o for c in footer for o in c["observations"]}
    assert values["+358201234560"]["channel_status"] == "published_general"
    assert oy["model_calls"] and all(m["cost_eur"] == 0 for m in oy["model_calls"])
    status = system.job(jobs["fixture_oy"])
    assert status["state"] == "completed" and status["completion_reason"] == "frontier_exhausted"
    assert status["coverage"]["confirmation"] == "unverified"
    assert status["counts"]["persons"] == len(found)


def test_country_focus_and_unapproved_host(
    tmp_path: Path, argus: contract_server.ContractServer, site: ThreadingHTTPServer,
    model: FakeModelServer,
) -> None:
    system, jobs = run_batch(tmp_path, argus, site, model)
    nordtec = persons(system.contacts(jobs["nordtec"]))
    for person in gold("nordtec")["persons"]:
        if person["priority"]:
            assert nordtec[person["name"]]["phone"]["normalized_value"] == person["phone"]
    vogel = persons(system.contacts(jobs["vogel"]))
    for person in gold("vogel")["persons"]:
        if person["priority"]:
            assert vogel[person["name"]]["email"]["normalized_value"] == person["email"]
    katsa = system.job(jobs["katsa"])
    assert katsa["state"] == "partial" and katsa["completion_reason"] == "unresolved_access"
    assert [g["reason"] for g in katsa["gaps"]] == ["domain_ownership_unresolved"]
    assert system.contacts(jobs["katsa"])["contacts"] == []
