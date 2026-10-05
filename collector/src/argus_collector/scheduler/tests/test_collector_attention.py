"""A bot check that does not clear: needs_attention, Huomio data, the owner's Jatka."""

from __future__ import annotations

from pathlib import Path

from argus_collector.scheduler import contract as scheduler
from argus_collector.scheduler.tests.stands import System, gold, heartbeat, make_collector, wait_for
from argus_collector.walk.tests.fake_policy import RankedPolicy
from collector.tests.fake_model_server import FakeModelServer
from contract_server import server as contract_server
from test_site import server


def local_state(collector: scheduler.Collector) -> str:
    rows = collector.queue_view().rows
    return rows[0].state if rows else ""


def test_bot_check_waits_for_the_owner_and_the_run_goes_on(tmp_path: Path) -> None:
    stuck = server.start(port=0, variant="challenge-stuck")
    port = stuck.server_address[1]
    argus = contract_server.start(port=0)
    fake = FakeModelServer(RankedPolicy(gold("ledvance")["persons"])).start()
    system = System(argus)
    site = stuck
    collector = make_collector(tmp_path, argus, fake.endpoint)
    try:
        job_id = system.batch(stuck, ["ledvance"])["ledvance"]
        collector.deliverer.start()
        collector.start()
        wait_for(lambda: local_state(collector) == "needs_attention", timeout_s=180)
        wait_for(lambda: system.job(job_id)["state"] == "needs_attention")
        items = collector.attention_view()
        assert [i.company for i in items] == ["LEDVANCE Oy"] and "/fi-fi/" in items[0].url
        heartbeat(collector, argus)
        assert local_state(collector) == "needs_attention", "the lease is kept, no failure"
        stuck.shutdown()
        stuck.server_close()
        site = server.start(port=port)  # the owner passed the check in the work browser
        collector.attention_done(job_id)
        wait_for(lambda: system.job(job_id)["state"] == "completed", timeout_s=180)
        wait_for(lambda: collector.delivery_view().pending == 0)
        status = system.job(job_id)
        assert status["runs_completed"] == 1, "the same run went on"
        people = [c for c in system.contacts(job_id)["contacts"] if c["entity_type"] == "person"]
        assert len(people) == len(gold("ledvance")["persons"])
        assert collector.attention_view() == []
    finally:
        collector.stop()
        collector.deliverer.stop()
        fake.stop()
        for srv in (site, argus):
            srv.shutdown()
            srv.server_close()
