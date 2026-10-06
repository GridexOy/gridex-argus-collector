"""End to end under Xvfb: Kaynnista in the real window walks the fixture site."""

from __future__ import annotations

import json
import time
import tkinter as tk
from collections.abc import Iterator
from pathlib import Path

import pytest

from argus_collector.runtime import contract as runtime
from argus_collector.ui import contract
from argus_collector.ui.app import PanelApp
from argus_collector.ui.tests.conftest import make_tk_root
from argus_collector.ui.tests.test_ui import display  # noqa: F401 - fixture reuse
from argus_collector.walk.tests.fake_policy import GoldPolicy
from collector.tests.fake_model_server import FakeModelServer
from test_site import server

WALK_TIMEOUT_S = 180


@pytest.fixture
def stands() -> Iterator[tuple[str, FakeModelServer]]:
    gold = json.loads(
        (runtime.repo_root() / "test_site" / "gold" / "fixture_oy.json").read_text("utf-8")
    )
    site = server.start(port=0)
    fake = FakeModelServer(GoldPolicy(gold["persons"])).start()
    try:
        yield server.base_url(site), fake
    finally:
        fake.stop()
        site.shutdown()
        site.server_close()


def write_config(home: Path, endpoint: str) -> None:
    lines = [
        "model:",
        f'  endpoint: "{endpoint}"',
        '  name: "fake-instruct"',
        "walk:",
        "  page_budget: 4",
    ]
    (home / "config.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def pump_until_done(app: PanelApp, root: tk.Tk) -> None:
    deadline = time.monotonic() + WALK_TIMEOUT_S
    while app.walk.walking and time.monotonic() < deadline:
        app.pump()
        root.update()
        time.sleep(0.1)
    app.pump()
    root.update()


def test_panel_drives_a_real_walk_with_the_fake_model(
    display: str,  # noqa: F811 - pytest fixture
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    stands: tuple[str, FakeModelServer],
) -> None:
    site_url, fake = stands
    monkeypatch.setenv("ARGUS_COLLECTOR_HOME", str(tmp_path))
    write_config(tmp_path, fake.endpoint)
    root = make_tk_root()
    try:
        app = contract.create_app(root)
        assert app.view.collect.status_label.cget("text") == "Ei keruuta käynnissä"
        app.walk.start(site_url)
        assert app.walk.walking and not app.view.is_enabled("start")
        pump_until_done(app, root)
        assert not app.walk.walking
        status = app.view.collect.status_label.cget("text")
        assert status == "Tavoite saavutettu: 3 henkilöä, 6 kanavaa", (
            "contact.html: three sales people with a phone and an email each end the walk")
        assert app.view.collect.row_count() == 3
        table = app.view.collect.table
        first = table.item(table.get_children()[0], "values")
        assert first[0] and first[-1].startswith("http://127.0.0.1:")
    finally:
        root.destroy()
