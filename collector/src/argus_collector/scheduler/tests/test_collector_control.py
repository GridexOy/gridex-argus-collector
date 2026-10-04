"""Pair A3.2-A3.4: ARGUS commands through the heartbeat, STOP, the journal."""

from __future__ import annotations

from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from argus_collector.scheduler.tests.stands import (
    System,
    heartbeat,
    make_collector,
    wait_for,
)
from collector.tests.fake_model_server import FakeModelServer
from contract_server import server as contract_server


def test_pause_resume_cancel_are_applied_and_acknowledged(
    tmp_path: Path, argus: contract_server.ContractServer, site: ThreadingHTTPServer,
    model: FakeModelServer, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_COLLECTOR_HOME", str(tmp_path / "home"))
    system = System(argus)
    jobs = system.batch(site, ["fixture_oy", "nordtec"])
    first, second = jobs["fixture_oy"], jobs["nordtec"]
    collector = make_collector(tmp_path, argus, model.endpoint)
    collector.deliverer.start()
    collector.start()
    wait_for(lambda: collector.running_job == first)
    paused = system.control(first, "pause")
    cancelled = system.control(second, "cancel")
    heartbeat(collector, argus)
    wait_for(lambda: not collector.walking)
    states = {r.job_id: r.state for r in collector.queue_view().rows}
    assert states == {first: "paused", second: "cancelled"}
    heartbeat(collector, argus)  # carries the acknowledgements
    commands = argus.stand.state["commands"]
    assert commands[paused["command_id"]]["ack"]["status"] == "applied"
    assert commands[cancelled["command_id"]]["ack"]["status"] == "applied"
    system.control(first, "resume")
    heartbeat(collector, argus)
    wait_for(lambda: system.job(first)["state"] == "completed")
    wait_for(lambda: collector.delivery_view().pending == 0)
    collector.stop()
    collector.deliverer.stop()
    assert system.job(second)["state"] == "cancelled"
    assert system.contacts(second)["contacts"] == [], "a cancelled job is not walked"
    assert system.contacts(first)["rejected"] == []
    log = "".join(p.read_text("utf-8") for p in (tmp_path / "home" / "logs").glob("*.log"))
    for channel in ("http", "browser", "extraction", "delivery", "model"):
        assert f" {channel}: " in log, channel
    assert "@" not in log, "no email address (contact value) in the journal"


def test_stop_file_stops_walking_and_claiming_but_not_delivery(
    tmp_path: Path, argus: contract_server.ContractServer, site: ThreadingHTTPServer,
    model: FakeModelServer,
) -> None:
    stop = tmp_path / "STOP"
    system = System(argus)
    job_id = system.batch(site, ["fixture_oy"])["fixture_oy"]
    collector = make_collector(tmp_path, argus, model.endpoint,
                               lambda: [stop] if stop.exists() else [])
    collector.deliverer.start()
    collector.start()
    wait_for(lambda: any(r.persons > 0 for r in collector.queue_view().rows))
    stop.write_text("", encoding="utf-8")
    wait_for(lambda: not collector.walking and not collector.collecting)
    later = system.batch(site, ["nordtec"])["nordtec"]
    wait_for(lambda: collector.delivery_view().pending == 0)
    assert system.job(later)["state"] == "queued", "nothing is claimed after STOP"
    assert collector.queue_view().rows[0].state == "stopped"
    assert system.job(job_id)["counts"]["persons"] > 0, "what was found got delivered"
    collector.deliverer.stop()
