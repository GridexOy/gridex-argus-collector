"""WINLOG 06.10.2026 (Blåkläder): the walk was over, the outbox still held the people after
seq 23, the lease ran out (lease_expired) and they never reached ARGUS. A finished job
keeps its lease in every heartbeat while its run has events to send."""

from __future__ import annotations

from datetime import timedelta
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from argus_collector.scheduler.tests.stands import System, heartbeat, make_collector, wait_for
from argus_collector.scheduler.tests.test_collector_recovery import (
    DONE,
    PERSONS,
    Clock,
    assert_clean,
)
from collector.tests.fake_model_server import FakeModelServer
from contract_server import server as contract_server


def test_the_lease_lives_until_the_tail_is_delivered(
    tmp_path: Path, site: ThreadingHTTPServer, model: FakeModelServer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_COLLECTOR_HOME", str(tmp_path / "home"))
    clock = Clock()
    argus = contract_server.start(port=0, now=clock)
    try:
        system = System(argus)
        job_id = system.batch(site, ["fixture_oy"])["fixture_oy"]
        collector = make_collector(tmp_path, argus, model.endpoint)
        collector.start()  # no delivery yet: the whole run waits in the outbox
        wait_for(lambda: bool(collector.queue_view().rows)
                 and collector.queue_view().rows[0].state in DONE)
        collector.stop()
        assert [j.job_id for j in collector.heartbeat_fields().active_jobs] == [job_id]
        for _ in range(4):  # 480 s: the 180 s lease would have run out twice
            clock.offset += timedelta(seconds=120)
            heartbeat(collector, argus)
        collector.deliverer.start()
        wait_for(lambda: collector.delivery_view().pending == 0)
        collector.deliverer.stop()
        assert_clean(system, job_id)
        assert system.contacts(job_id)["rejected"] == [] and PERSONS > 0
        assert collector.heartbeat_fields().active_jobs == [], "delivered: the lease is let go"
        log = "".join(p.read_text("utf-8") for p in (tmp_path / "home" / "logs").glob("*"))
        assert "lease_expired" not in log
    finally:
        argus.shutdown()
        argus.server_close()
