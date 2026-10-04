"""End to end under Xvfb: Testaa yhteys drives a real heartbeat to contract_server."""

from __future__ import annotations

import time
import tkinter as tk
from collections.abc import Iterator
from pathlib import Path

import pytest

from argus_collector.ui import contract
from argus_collector.ui.app import PanelApp
from argus_collector.ui.tests.conftest import make_tk_root
from argus_collector.ui.tests.test_ui import display  # noqa: F401 - fixture reuse
from argus_collector.worker_auth import contract as worker_auth
from contract_server import server as contract_server

TOKEN = "test-token-abc"
WORKER_ID = "worker-main-pc"
HEARTBEAT_TIMEOUT_S = 15


@pytest.fixture
def running() -> Iterator[contract_server.ContractServer]:
    srv = contract_server.start(port=0, tokens={TOKEN: WORKER_ID})
    try:
        yield srv
    finally:
        srv.shutdown()
        srv.server_close()


def write_config(home: Path, base_url: str) -> None:
    lines = [f'argus:\n  base_url: "{base_url}"', "network:\n  proxy: direct"]
    (home / "config.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def pump_until(app: PanelApp, root: tk.Tk, predicate: object) -> None:
    deadline = time.monotonic() + HEARTBEAT_TIMEOUT_S
    while not predicate() and time.monotonic() < deadline:  # type: ignore[operator]
        app.pump()
        root.update()
        time.sleep(0.1)
    app.pump()
    root.update()


def test_testaa_yhteys_connects_to_the_contract_server(
    display: str,  # noqa: F811 - pytest fixture
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    running: contract_server.ContractServer,
) -> None:
    monkeypatch.setenv("ARGUS_COLLECTOR_HOME", str(tmp_path))
    write_config(tmp_path, contract_server.base_url(running))
    root = make_tk_root()
    try:
        app = contract.create_app(root)
        assert app.view.connection.state_label.cget("text") == "Ei yhteyttä"
        app.connection.test_connection(contract_server.base_url(running), WORKER_ID, TOKEN)
        pump_until(app, root, lambda: app.connection.state.status == "ok")
        assert app.view.connection.state_label.cget("text") == "Yhdistetty"
        assert app.connection.state.last_heartbeat is not None
        assert running.registry.seen_at(WORKER_ID) is not None
        assert worker_auth.load_connection() == worker_auth.SavedConnection(
            contract_server.base_url(running), WORKER_ID
        )
        assert worker_auth.load_token() == TOKEN
    finally:
        root.destroy()


def test_testaa_yhteys_shows_rejected_for_a_bad_token(
    display: str,  # noqa: F811 - pytest fixture
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    running: contract_server.ContractServer,
) -> None:
    monkeypatch.setenv("ARGUS_COLLECTOR_HOME", str(tmp_path))
    write_config(tmp_path, contract_server.base_url(running))
    root = make_tk_root()
    try:
        app = contract.create_app(root)
        app.connection.test_connection(
            contract_server.base_url(running), WORKER_ID, "not-a-real-token"
        )
        pump_until(app, root, lambda: app.connection.state.status == "rejected")
        assert app.view.connection.state_label.cget("text") == "Tunnus hylätty"
        assert worker_auth.load_token() is None
    finally:
        root.destroy()
