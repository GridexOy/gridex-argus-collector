"""End to end under Xvfb: Kaynnista claims an ARGUS job, Jono and Lahetys follow it."""

from __future__ import annotations

import json
import time
import tkinter as tk
import urllib.request
import uuid
from collections.abc import Callable, Iterator
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from argus_collector.runtime import contract as runtime
from argus_collector.ui import contract
from argus_collector.ui.app import PanelApp
from argus_collector.ui.tests.conftest import make_tk_root
from argus_collector.ui.tests.test_ui import display  # noqa: F401 - fixture reuse
from argus_collector.walk.tests.fake_policy import RankedPolicy
from collector.tests.fake_model_server import FakeModelServer
from contract_server import server as contract_server
from contract_server import stand
from test_site import companies, server

TIMEOUT_S = 240
DIRECT = urllib.request.build_opener(urllib.request.ProxyHandler({}))


@pytest.fixture
def stands() -> Iterator[tuple[contract_server.ContractServer, ThreadingHTTPServer, str]]:
    gold = json.loads(
        (runtime.repo_root() / "test_site" / "gold" / "fixture_oy.json").read_text("utf-8")
    )
    site, argus = server.start(port=0), contract_server.start(port=0)
    fake = FakeModelServer(RankedPolicy(gold["persons"])).start()
    try:
        yield argus, site, fake.endpoint
    finally:
        for srv in (fake,):
            srv.stop()
        for http in (site, argus):
            http.shutdown()
            http.server_close()


def create_batch(argus: contract_server.ContractServer, site: ThreadingHTTPServer) -> None:
    item = companies.companies(site.server_address[1])[0]
    body = {"client_request_id": str(uuid.uuid4()), "companies": [stand.company_input(item, None)]}
    req = urllib.request.Request(
        contract_server.base_url(argus) + "/api/collector/batches",
        data=json.dumps(body).encode("utf-8"), method="POST",
        headers={"Authorization": "Bearer system-token-xyz", "Content-Type": "application/json"},
    )
    with DIRECT.open(req, timeout=10) as resp:
        assert resp.status == 201


def pump_until(app: PanelApp, root: tk.Tk, predicate: Callable[[], bool]) -> None:
    deadline = time.monotonic() + TIMEOUT_S
    while not predicate() and time.monotonic() < deadline:
        app.pump()
        root.update()
        time.sleep(0.1)
    app.pump()
    root.update()
    assert predicate(), "the panel did not reach the expected state"


def test_kaynnista_collects_an_argus_job_into_jono_and_lahetys(
    display: str,  # noqa: F811 - pytest fixture
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    stands: tuple[contract_server.ContractServer, ThreadingHTTPServer, str],
) -> None:
    argus, site, endpoint = stands
    monkeypatch.setenv("ARGUS_COLLECTOR_HOME", str(tmp_path))
    config = (f'model:\n  endpoint: "{endpoint}"\n  name: "fake-instruct"\n'
              "network:\n  proxy: direct\n")
    (tmp_path / "config.yaml").write_text(config, encoding="utf-8")
    create_batch(argus, site)
    root = make_tk_root()
    try:
        app = contract.create_app(root)
        app.connection.pair(contract_server.pairing_key(
            contract_server.base_url(argus), "worker-main-pc", "test-token-abc"))
        pump_until(app, root, lambda: app.connection.connected)
        app.collect.start()
        rows = app.view.queue.rows
        pump_until(app, root, lambda: bool(rows()) and rows()[0][-1].startswith("Valmis"))
        pump_until(app, root, lambda: app.view.delivery.state_label.cget("text") == "Lähetetty")
        company, _stage, persons, channels, sources, _tila = rows()[0]
        assert company == "Fixture Oy" and int(persons) == 7
        assert int(channels) >= 14 and int(sources) >= 4
        status = app.view.collect.status_label.cget("text")
        assert status.startswith("Keruu valmis:"), "the end of the job walk replaces the page line"
        counts = app.view.delivery.counts_label.cget("text")
        assert counts.startswith("Odottaa lähetystä: 0 · Lähetysvirhe: 0")
        app.collect.stop()
        assert app.view.collect.row_count() == 7, "the walk's rows are shown as before"
    finally:
        root.destroy()
