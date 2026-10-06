"""One Chrome for a whole collection (owner 06.10.2026): three companies, one start."""

from __future__ import annotations

import re
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from argus_collector.runtime import contract as runtime
from argus_collector.scheduler.tests.stands import System, make_collector, wait_for
from collector.tests.fake_model_server import FakeModelServer
from contract_server import server as contract_server

COMPANIES = ["fixture_oy", "nordtec", "reimax"]
START_RE = re.compile(r"browser: job (\S+): chrome start=(\d+) ms shared=(\w+)")


def journal_text() -> str:
    return "".join(p.read_text("utf-8") for p in (runtime.user_data_dir() / "logs").glob("*.log"))


def test_three_companies_one_chrome_start(
    tmp_path: Path, argus: contract_server.ContractServer, site: ThreadingHTTPServer,
    model: FakeModelServer, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_COLLECTOR_HOME", str(tmp_path / "home"))
    system = System(argus)
    collector = make_collector(tmp_path, argus, model.endpoint, stop_at_goal=True)
    collector.deliverer.start()
    collector.start()
    try:
        jobs = system.batch(site, COMPANIES)
        done = ("completed", "partial")
        wait_for(lambda: all(system.job(j)["state"] in done for j in jobs.values()))
    finally:
        collector.stop(wait_s=30.0)  # as when the panel closes
        collector.deliverer.stop()
    assert "chrome closed" in journal_text(), "Chrome closed before stop() returned"
    starts = {job: (int(ms), shared) for job, ms, shared in START_RE.findall(journal_text())}
    assert set(starts) == set(jobs.values()), starts
    assert all(shared == "yes" for _ms, shared in starts.values())
    assert sorted(ms > 0 for ms, _shared in starts.values()) == [False, False, True], (
        "Chrome starts for the first company only")
    assert re.search(r"chrome closed: 1 starts, \d+ ms", journal_text())
