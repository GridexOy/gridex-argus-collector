"""End to end under Xvfb: a pasted pairing key connects to contract_server, and stays."""

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


def write_config(home: Path) -> None:
    (home / "config.yaml").write_text("network:\n  proxy: direct\n", encoding="utf-8")


def key_of(srv: contract_server.ContractServer, token: str = TOKEN) -> str:
    return contract_server.pairing_key(contract_server.base_url(srv), WORKER_ID, token)


def paste(app: PanelApp, key: str) -> None:
    """What the owner does: paste the key into Paritusavain and press Yhdista."""
    app.view.connection.key_var.set(key)
    app.view.connection.connect_button.invoke()


def pump_until(app: PanelApp, root: tk.Tk, predicate: object) -> None:
    deadline = time.monotonic() + HEARTBEAT_TIMEOUT_S
    while not predicate() and time.monotonic() < deadline:  # type: ignore[operator]
        app.pump()
        root.update()
        time.sleep(0.1)
    app.pump()
    root.update()


def test_pairing_key_connects_and_is_saved(
    display: str,  # noqa: F811 - pytest fixture
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    running: contract_server.ContractServer,
) -> None:
    monkeypatch.setenv("ARGUS_COLLECTOR_HOME", str(tmp_path))
    write_config(tmp_path)
    root = make_tk_root()
    try:
        app = contract.create_app(root)
        block = app.view.connection
        assert block.state_label.cget("text") == "Ei yhteyttä"
        assert block.paired_label.cget("text").startswith("Ei paritettu")
        paste(app, key_of(running))
        assert block.key_var.get() == "", "the key holds the token: emptied at once"
        pump_until(app, root, lambda: app.connection.state.status == "ok")
        assert block.state_label.cget("text") == "Yhdistetty"
        address = contract_server.base_url(running)
        assert block.paired_label.cget("text") == (
            f"Paritettu: {address} · {WORKER_ID} · tunnus **********-abc"
        )
        assert running.registry.seen_at(WORKER_ID) is not None
        assert worker_auth.load_connection() == worker_auth.SavedConnection(address, WORKER_ID)
        assert worker_auth.load_token() == TOKEN
    finally:
        root.destroy()


def test_saved_pairing_connects_by_itself_at_the_next_start(
    display: str,  # noqa: F811 - pytest fixture
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    running: contract_server.ContractServer,
) -> None:
    monkeypatch.setenv("ARGUS_COLLECTOR_HOME", str(tmp_path))
    write_config(tmp_path)
    worker_auth.save_pairing(worker_auth.parse_pairing_key(key_of(running)))
    root = make_tk_root()
    try:
        app = contract.create_app(root)
        app.connection.start_if_saved()  # what run_panel does after building the window
        assert app.view.connection.state_label.cget("text") == "Tarkistetaan…"
        pump_until(app, root, lambda: app.connection.state.status == "ok")
        assert app.view.connection.state_label.cget("text") == "Yhdistetty"
        assert running.registry.seen_at(WORKER_ID) is not None
    finally:
        root.destroy()


def test_a_bad_key_is_refused_without_a_call_and_keeps_the_pairing(
    display: str,  # noqa: F811 - pytest fixture
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    running: contract_server.ContractServer,
) -> None:
    monkeypatch.setenv("ARGUS_COLLECTOR_HOME", str(tmp_path))
    write_config(tmp_path)
    root = make_tk_root()
    try:
        app = contract.create_app(root)
        paste(app, "https://argus.example.fi worker-main-pc test-token-abc")
        app.pump()
        root.update()
        error = app.view.connection.key_error_label
        assert error.cget("text").startswith("Paritusavain ei kelpaa: muoto on argus://pair")
        assert error.winfo_ismapped()
        assert running.registry.seen_at(WORKER_ID) is None
        assert worker_auth.load_connection() is None and worker_auth.load_token() is None
        paste(app, "argus://pair?url=http://argus.example.fi&worker=w&token=t")
        assert "https://" in error.cget("text")
        paste(app, key_of(running))
        pump_until(app, root, lambda: app.connection.state.status == "ok")
        assert not error.winfo_ismapped()
    finally:
        root.destroy()


def test_a_rejected_token_shows_tunnus_hylatty(
    display: str,  # noqa: F811 - pytest fixture
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    running: contract_server.ContractServer,
) -> None:
    monkeypatch.setenv("ARGUS_COLLECTOR_HOME", str(tmp_path))
    write_config(tmp_path)
    root = make_tk_root()
    try:
        app = contract.create_app(root)
        paste(app, key_of(running, "not-a-real-token"))
        pump_until(app, root, lambda: app.connection.state.status == "rejected")
        assert app.view.connection.state_label.cget("text") == "Tunnus hylätty"
        assert not app.connection.connected
    finally:
        root.destroy()


def test_argus_down_keeps_the_last_heartbeat_and_shows_ei_verkkoa(
    display: str,  # noqa: F811 - pytest fixture
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    srv = contract_server.start(port=0, tokens={TOKEN: WORKER_ID})
    key = key_of(srv)
    monkeypatch.setenv("ARGUS_COLLECTOR_HOME", str(tmp_path))
    write_config(tmp_path)
    root = make_tk_root()
    try:
        app = contract.create_app(root)
        paste(app, key)
        pump_until(app, root, lambda: app.view.delivery.state_label.cget("text") == "Lähetetty")
        seen = app.view.connection.heartbeat_label.cget("text")
        assert seen.startswith("Viimeksi:")
        srv.shutdown()
        srv.server_close()
        app.connection.start_if_saved()  # the next start: the saved key, ARGUS gone
        pump_until(app, root, lambda: app.view.delivery.state_label.cget("text") == "Ei verkkoa")
        assert app.view.delivery.state_label.cget("text") == "Ei verkkoa", "nothing pending"
        assert app.view.connection.state_label.cget("text").startswith("Ei verkkoa")
        assert app.view.connection.heartbeat_label.cget("text") == seen
    finally:
        root.destroy()
