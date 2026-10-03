"""Panel tests: props without a display, and the real window under Xvfb."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from argus_collector.diagnostics import contract as diagnostics
from argus_collector.diagnostics.tests.test_diagnostics import sample_document
from argus_collector.extraction.contract import Contact, VerifiedField
from argus_collector.runtime import contract as runtime
from argus_collector.runtime import service as runtime_service
from argus_collector.ui import contract, repository, service
from argus_collector.ui.tests.conftest import make_tk_root
from argus_collector.walk.contract import WalkEvent


@pytest.fixture(scope="module")
def msgs() -> repository.Messages:
    return repository.load_messages()


def _status(raw: dict[str, str] | None) -> runtime.VersionStatus:
    return runtime_service.version_status("0.4.1.0", raw)


def version_ok() -> runtime.VersionStatus:
    return _status({"version": "0.4.1.0", "commit": "abc1234", "built_at": "2026-10-03T14:32:00"})


def ready_report() -> diagnostics.Report:
    doc = sample_document()
    doc["model"].update({"reachable": True, "state": "gpu"})
    doc["gpu"]["memory_used_mb"] = 9000
    return diagnostics.parse_report_json(json.dumps(doc))


def test_props_show_required_states(msgs: repository.Messages) -> None:
    report = diagnostics.parse_report_json(json.dumps(sample_document()))
    props = service.build_props(msgs, version_ok(), report, None, None)
    assert props.version.text == "cv0.4.1.0 (3.10.2026 klo 14.32) abc1234"
    assert props.connection_state.text == "Ei yhteyttä"
    assert props.collect.site_url_label == "Yrityksen verkkosivu"
    assert (props.collect.start_label, props.collect.stop_label) == ("Käynnistä", "Pysäytä")
    assert not props.collect.start_enabled and not props.collect.stop_enabled
    assert props.collect.hint == "Keruu vaatii paikallisen mallin ja Chromen (katso Resurssit)"
    assert props.collect.columns == ["Nimi", "Titteli", "Puhelin", "Sähköposti", "Lähde"]
    texts = [line.text for line in props.resources]
    assert "Chrome: käytettävissä" in texts and "Malli: ei ladattu" in texts
    assert any(
        t.startswith("Malli qwen2.5:14b-instruct @ http://127.0.0.1:11434/v1") for t in texts
    )
    assert props.stop_banner is None


def test_start_enabled_only_with_model_and_chrome(msgs: repository.Messages) -> None:
    ready = service.build_props(msgs, version_ok(), ready_report(), None, None)
    assert ready.collect.start_enabled and ready.collect.hint == ""
    walking = service.build_props(msgs, version_ok(), ready_report(), None, None, walking=True)
    assert not walking.collect.start_enabled and walking.collect.stop_enabled
    assert not walking.open_browser_enabled
    stopped = service.build_props(msgs, version_ok(), ready_report(), None, "/x/STOP")
    assert (
        not stopped.collect.start_enabled and stopped.collect.hint == "STOP-tiedosto estää keruun"
    )
    assert stopped.stop_banner is not None and stopped.stop_banner.level == service.LEVEL_ERROR


def test_props_show_diagnostics_error_in_red(msgs: repository.Messages) -> None:
    props = service.build_props(msgs, version_ok(), None, "diagnose.ps1 exit 1: boom", None)
    assert props.resources == [
        service.Line("Resurssien tarkistus epäonnistui: diagnose.ps1 exit 1: boom", "error")
    ]
    assert service.build_props(msgs, _status(None), None, None, None).version.text == (
        "cv0.4.1.0 (ei asennustietoa)"
    )


def contact_event() -> WalkEvent:
    name = VerifiedField("Anna Virtanen", "Anna Virtanen", 0, 13, "text")
    phone = VerifiedField("+358401234567", "040 123 4567", 20, 32, "href:tel")
    return WalkEvent(
        "contact", url="http://h/contact.html", contact=Contact(name, None, phone, None)
    )


def test_walk_event_lines_and_rows(msgs: repository.Messages) -> None:
    page = WalkEvent("page", url="http://h/", page_no=2, budget=15)
    assert service.walk_event_line(msgs, page) == ("Sivu 2/15: http://h/", "info")
    click = WalkEvent("step", step="click", detail="Näytä yhteystiedot")
    assert service.walk_event_line(msgs, click) == ("Napsautetaan: Näytä yhteystiedot", "info")
    failed = WalkEvent("step", step="model", detail="cards failed: HTTP 500")
    assert service.walk_event_line(msgs, failed) == ("Mallivirhe: cards failed: HTTP 500", "error")
    error = WalkEvent("error", error="BrowserLaunchError: boom")
    assert service.walk_event_line(msgs, error) == ("Keruuvirhe: BrowserLaunchError: boom", "error")
    assert service.walk_event_line(msgs, contact_event()) is None
    assert service.contact_row(contact_event()) == (
        "Anna Virtanen",
        "",
        "+358401234567",
        "",
        "http://h/contact.html",
    )


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


def test_window_renders_keruu_block_and_live_rows(
    display: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ARGUS_COLLECTOR_HOME", str(tmp_path))
    root = make_tk_root()
    try:
        app = contract.create_app(root)
        root.update()
        assert root.title() == "ARGUS Selain"
        for name in ("start", "pause", "stop"):
            assert not app.view.is_enabled(name), name
        assert app.view.is_enabled("open_browser")
        assert app.view.connection_label.cget("text") == "Yhteys: Ei yhteyttä"
        expected_prefix = f"cv{runtime.current_version_status().file_version} ("
        assert app.view.version_label.cget("text").startswith(expected_prefix)
        app.view.collect.url_var.set("not a url")
        app.walk.start("not a url")
        assert app.view.collect.status_label.cget("text") == "Virheellinen osoite: not a url"
        app.walk.on_event(contact_event())
        app.walk.on_event(WalkEvent("page", url="http://h/", page_no=1, budget=15))
        root.update()
        assert app.view.collect.row_count() == 1
        assert app.view.collect.found_label.cget("text") == "Löydetty: 1 yhteystietoa"
        assert app.view.collect.status_label.cget("text") == "Sivu 1/15: http://h/"
        app._collect()
        app.pump()
        root.update()
        texts = [label.cget("text") for label in app.view.resource_labels]
        assert any(t.startswith("Malli: ") for t in texts)
        assert not any("unknown" in t.lower() for t in texts)
    finally:
        root.destroy()
