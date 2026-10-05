"""The pilot tables from a real batch: numbers per company, threshold, 10 phones checked."""

from __future__ import annotations

from collections.abc import Iterator
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from argus_collector.pilot import contract as pilot
from argus_collector.scheduler.tests.stands import System, gold_persons, make_collector, wait_for
from argus_collector.storage import contract as storage
from argus_collector.walk.tests.fake_policy import RankedPolicy
from collector.tests.fake_model_server import FakeModelServer
from contract_server import server as contract_server
from test_site import server


@pytest.fixture
def stands() -> Iterator[tuple[ThreadingHTTPServer, contract_server.ContractServer, str]]:
    site, argus = server.start(port=0), contract_server.start(port=0)
    fake = FakeModelServer(RankedPolicy(gold_persons())).start()
    try:
        yield site, argus, fake.endpoint
    finally:
        fake.stop()
        for srv in (site, argus):
            srv.shutdown()
            srv.server_close()


def test_report_of_a_batch(
    tmp_path: Path, stands: tuple[ThreadingHTTPServer, contract_server.ContractServer, str]
) -> None:
    site, argus, endpoint = stands
    system = System(argus)
    jobs = system.batch(site, ["fixture_oy", "nordtec"])
    collector = make_collector(tmp_path, argus, endpoint)
    collector.deliverer.start()
    collector.start()
    wait_for(lambda: all(system.job(j)["state"] == "completed" for j in jobs.values()))
    wait_for(lambda: collector.delivery_view().pending == 0)
    collector.stop()
    collector.deliverer.stop()
    conn = storage.connect(tmp_path / "collector.db")
    try:
        found = pilot.report(conn)
    finally:
        conn.close()
    rows = {r.company: r for r in found.rows}
    assert set(rows) == {"Fixture Oy", "Nordtec AB"}
    fixture = rows["Fixture Oy"]
    assert fixture.persons == 7 and fixture.pages >= 4 and fixture.model_calls > 0
    assert fixture.wall_seconds >= fixture.active_seconds > 0
    assert fixture.direct > 0 and found.threshold_met
    assert len(found.phones) == 10
    assert all(p.host_ok and p.quote_ok for p in found.phones), found.phones
    text = pilot.render_markdown(found)
    assert "| Fixture Oy | completed (frontier_exhausted) |" in text
    assert "threshold 50 %: met" in text
