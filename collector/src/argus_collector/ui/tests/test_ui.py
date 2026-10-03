"""Panel tests: props without a display, and the real window under Xvfb."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import tkinter as tk
from collections.abc import Iterator
from pathlib import Path

import pytest

from argus_collector.diagnostics import contract as diagnostics
from argus_collector.diagnostics.tests.test_diagnostics import sample_document
from argus_collector.runtime import contract as runtime
from argus_collector.runtime import service as runtime_service
from argus_collector.ui import contract, repository, service


@pytest.fixture(scope="module")
def msgs() -> repository.Messages:
    return repository.load_messages()


def _status(raw: dict[str, str] | None) -> runtime.VersionStatus:
    return runtime_service.version_status("0.0.1.0", raw)


def version_ok() -> runtime.VersionStatus:
    return _status({"version": "0.0.1.0", "commit": "abc1234", "built_at": "2026-10-03T14:32:00"})


def test_props_show_required_s0_states(msgs: repository.Messages) -> None:
    report = diagnostics.parse_report_json(json.dumps(sample_document()))
    props = service.build_props(msgs, version_ok(), report, None, None)
    assert props.version.text == "cv0.0.1.0 (3.10.2026 klo 14.32) abc1234"
    assert props.connection_state.text == "Ei yhteyttä"
    assert props.collecting_enabled is False
    assert (props.start_label, props.pause_label, props.stop_label) == (
        "Käynnistä",
        "Keskeytä",
        "Pysäytä",
    )
    texts = [line.text for line in props.resources]
    assert "Chrome: käytettävissä" in texts
    assert "Malli: ei ladattu" in texts
    assert any(t.startswith("NVIDIA: NVIDIA GeForce RTX 4090") for t in texts)
    assert any(t.startswith("Levy C:") for t in texts)
    assert props.open_browser_label == "Avaa työselain"
    assert props.stop_banner is None


def test_props_without_install_and_with_stop(msgs: repository.Messages) -> None:
    props = service.build_props(msgs, _status(None), None, None, "/x/STOP")
    assert props.version.text == "cv0.0.1.0 (ei asennustietoa)"
    assert props.resources[0].text == "Tarkistetaan…"
    assert props.stop_banner is not None and "/x/STOP" in props.stop_banner.text
    assert props.stop_banner.level == service.LEVEL_ERROR


def test_props_show_diagnostics_error_in_red(msgs: repository.Messages) -> None:
    props = service.build_props(msgs, version_ok(), None, "diagnose.ps1 exit 1: boom", None)
    assert props.resources == [
        service.Line("Resurssien tarkistus epäonnistui: diagnose.ps1 exit 1: boom", "error")
    ]


def test_props_version_mismatch_is_error(msgs: repository.Messages) -> None:
    raw = {"version": "0.0.0.0", "commit": "abc1234", "built_at": "2026-10-03T14:32:00"}
    props = service.build_props(msgs, _status(raw), None, None, None)
    assert props.version.level == service.LEVEL_ERROR
    assert "Versiovirhe" in props.version.text


def test_missing_key_raises(msgs: repository.Messages) -> None:
    with pytest.raises(KeyError):
        msgs.t("no.such.key")


@pytest.fixture(scope="module")
def display() -> Iterator[str]:
    if os.environ.get("DISPLAY") or os.name == "nt":
        yield os.environ.get("DISPLAY", "")
        return
    xvfb = shutil.which("Xvfb")
    if xvfb is None:
        pytest.skip("no DISPLAY and no Xvfb")
    proc = subprocess.Popen([xvfb, ":99", "-screen", "0", "1024x768x24"])
    os.environ["DISPLAY"] = ":99"
    time.sleep(0.8)
    try:
        yield ":99"
    finally:
        proc.terminate()
        os.environ.pop("DISPLAY", None)


def test_window_renders_strings_and_disabled_buttons(
    display: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ARGUS_COLLECTOR_HOME", str(tmp_path))
    (tmp_path / "STOP").write_text("", encoding="utf-8")
    root = tk.Tk()
    try:
        app = contract.create_app(root)
        root.update()
        assert root.title() == "ARGUS Selain"
        for name in ("start", "pause", "stop"):
            assert not app.view.is_enabled(name), name
        assert app.view.is_enabled("open_browser")
        assert app.view.connection_label.cget("text") == "Yhteys: Ei yhteyttä"
        assert app.view.version_label.cget("text").startswith("cv0.0.1.0 (")
        assert "STOP" in app.view.stop_label.cget("text")
        app._collect()
        app.pump()
        root.update()
        texts = [label.cget("text") for label in app.view.resource_labels]
        assert any(t.startswith("Malli: ") for t in texts)
        assert any(t.startswith("Chrome: ") for t in texts)
        assert not any("unknown" in t.lower() for t in texts)
    finally:
        root.destroy()
