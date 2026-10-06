"""Reimax through the contract (owner 06.10.2026): addresses of the stated pattern.

ARGUS accepts the address the page's pattern gives each person (quote = the pattern
line) and derives `inferred` (oletettu) for it; the pattern is the company's
`email_pattern`, not a channel. A re-run whose known contacts carry that address
sends it `reconfirmed`: the same row gets one more source, not a second row.
"""

from __future__ import annotations

from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

from argus_collector.scheduler import contract as scheduler
from argus_collector.scheduler.tests.stands import System, gold, make_collector, wait_for
from collector.tests.fake_model_server import FakeModelServer
from contract_server import server as contract_server

GOLD = gold("reimax")
EMAILS = {p["name"]: p["email"] for p in GOLD["persons"]}


def run(collector: scheduler.Collector, system: System, job_id: str) -> dict[str, Any]:
    wait_for(lambda: system.job(job_id)["state"] in ("completed", "partial", "failed"))
    wait_for(lambda: collector.delivery_view().pending == 0)
    return system.job(job_id)


def emails(system: System) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for contact in system.company("reimax")["contacts"]:
        names = [o["normalized_value"] for o in contact["observations"]
                 if o["field"] == "full_name"]
        if contact["entity_type"] == "person" and names:
            out[names[0]] = [o for o in contact["observations"] if o["field"] == "email"]
    return out


def test_pattern_addresses_are_inferred_and_a_rerun_keeps_one_row(
    tmp_path: Path, argus: contract_server.ContractServer, site: ThreadingHTTPServer,
    model: FakeModelServer,
) -> None:
    system = System(argus)
    collector = make_collector(tmp_path, argus, model.endpoint, stop_at_goal=True)
    collector.deliverer.start()
    collector.start()
    try:
        first = system.batch(site, ["reimax"])["reimax"]
        assert run(collector, system, first)["state"] == "completed"
        assert collector.delivery_view().errors == 0, "ARGUS took every event"
        found = emails(system)
        assert set(found) == set(EMAILS)
        for name, rows in found.items():
            assert [(o["normalized_value"], o["channel_status"]) for o in rows] == [
                (EMAILS[name], "inferred")], name
            assert rows[0]["quote"] == GOLD["pattern"]["quote"]
        patterns = [o for c in system.company("reimax")["contacts"] for o in c["observations"]
                    if o["field"] == "email_pattern"]
        assert [(o["normalized_value"], o["channel_status"]) for o in patterns] == [
            (GOLD["pattern"]["value"], None)], "a pattern is no channel: no status"
        second = system.batch(site, ["reimax"], rerun="pattern: same row")["reimax"]
        run(collector, system, second)
    finally:
        collector.stop()
        collector.deliverer.stop()
    again = emails(system)
    for name, rows in again.items():
        assert len(rows) == 1, f"{name}: the known address is reconfirmed, not a second row"
        assert rows[0]["last_confirmed_at"] is not None, name
    patterns = [o for c in system.company("reimax")["contacts"] for o in c["observations"]
                if o["field"] == "email_pattern"]
    assert len(patterns) == 1 and patterns[0]["last_confirmed_at"], (
        "the pattern rides on the company's channel: reconfirmed on its row")
