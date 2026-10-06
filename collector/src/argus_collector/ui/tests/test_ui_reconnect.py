"""Under Xvfb (0.4.8.2): Yhdista uudelleen without a key; Yhdista with an empty field is silent."""

from __future__ import annotations

from pathlib import Path

import pytest

from argus_collector.ui import contract
from argus_collector.ui.tests.conftest import make_tk_root
from argus_collector.ui.tests.test_ui import display  # noqa: F401 - fixture reuse
from argus_collector.ui.tests.test_ui_connection import (
    key_of,
    paste,
    pump_until,
    running,  # noqa: F401 - fixture reuse
    write_config,
)
from contract_server import server as contract_server


def test_reconnect_button_and_an_empty_key_field(
    display: str,  # noqa: F811 - pytest fixture
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    running: contract_server.ContractServer,  # noqa: F811 - pytest fixture
) -> None:
    monkeypatch.setenv("ARGUS_COLLECTOR_HOME", str(tmp_path))
    write_config(tmp_path)
    root = make_tk_root()
    try:
        app = contract.create_app(root)
        block = app.view.connection
        assert block.reconnect_button.cget("text") == "Yhdistä uudelleen"
        assert block.reconnect_button.instate(["disabled"]), "no saved key yet"
        paste(app, "")
        app.pump()
        root.update()
        assert not block.key_error_label.winfo_ismapped(), "an empty field: no error"
        paste(app, key_of(running))
        pump_until(app, root, lambda: app.connection.state.status == "ok")
        assert block.reconnect_button.instate(["!disabled"])
        app.connection.state = app.connection.state.__class__(
            app.connection.state.address, app.connection.state.worker_id,
            app.connection.state.token, "error", "HTTP 0: timed out")
        app.refresh()
        block.reconnect_button.invoke()
        pump_until(app, root, lambda: app.connection.state.status == "ok")
        assert block.state_label.cget("text") == "Yhdistetty"
        assert block.heartbeat_label.cget("text").startswith("Viimeksi:")
    finally:
        app.connection.loop.stop()
        root.destroy()
