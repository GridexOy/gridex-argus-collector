"""Browser module: launch plan rules and a headless smoke against the test site."""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Iterator
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from argus_collector.browser import contract, service
from argus_collector.runtime import contract as runtime
from test_site import server


@pytest.fixture
def site() -> Iterator[ThreadingHTTPServer]:
    srv = server.start(port=0)
    try:
        yield srv
    finally:
        srv.shutdown()
        srv.server_close()


def test_plan_uses_installed_chrome_only_on_windows(tmp_path: Path) -> None:
    win = service.launch_plan(tmp_path, windows=True)
    other = service.launch_plan(tmp_path, windows=False, headless=True)
    assert win.channel == "chrome" and win.uses_installed_chrome and not win.headless
    assert other.channel is None and not other.uses_installed_chrome and other.headless
    assert service.launch_kwargs(win)["channel"] == "chrome"
    assert "channel" not in service.launch_kwargs(other)
    assert service.launch_kwargs(other)["user_data_dir"] == str(tmp_path)


def test_plan_for_this_machine_defaults_to_profile_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ARGUS_COLLECTOR_HOME", str(tmp_path))
    plan = contract.plan_for_this_machine()
    assert plan.user_data_dir == tmp_path / "browser-profile"
    assert plan.uses_installed_chrome == (os.name == "nt")


def test_describe_failure_is_one_line(tmp_path: Path) -> None:
    plan = service.launch_plan(tmp_path, windows=True)
    text = service.describe_failure(plan, RuntimeError("boom\nsecond line"))
    assert text == f"work browser (installed Chrome, profile {tmp_path}) failed: boom"


def test_launcher_command_shape() -> None:
    cmd = contract.launcher_command("http://127.0.0.1:1/", 8765)
    assert cmd[:3] == [sys.executable, "-m", "argus_collector.browser"]
    assert cmd[3:] == ["--url", "http://127.0.0.1:1/", "--serve-test-site", "8765"]


def test_smoke_opens_test_site_in_persistent_profile(
    site: ThreadingHTTPServer, tmp_path: Path
) -> None:
    profile = tmp_path / "profile"
    url = server.base_url(site) + "contact.html"
    result = contract.open_work_browser(
        url, headless=True, wait_until_closed=False, profile_dir=profile
    )
    assert result.url == url
    assert result.title == "Contact - Fixture Oy"
    assert result.user_data_dir == profile
    assert profile.is_dir() and any(profile.iterdir()), "profile must persist on disk"
    assert result.browser_version


def test_launch_error_is_reported_not_swallowed(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    with pytest.raises(contract.BrowserLaunchError, match="work browser"):
        contract.open_work_browser(
            "http://127.0.0.1:9/", headless=True, wait_until_closed=False, profile_dir=profile
        )


def test_cli_no_wait_prints_opened_line(site: ThreadingHTTPServer, tmp_path: Path) -> None:
    cmd = contract.launcher_command(server.base_url(site)) + [
        "--headless",
        "--no-wait",
        "--profile-dir",
        str(tmp_path / "profile"),
    ]
    env = contract.launcher_env()
    assert env["PYTHONPATH"].startswith(str(runtime.repo_root() / "collector" / "src"))
    done = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", timeout=90, env=env, check=False
    )
    assert done.returncode == 0, done.stderr
    assert '"opened": true' in done.stdout
    assert "Fixture Oy" in done.stdout


def test_walk_browser_observes_candidates_and_clicks(
    site: ThreadingHTTPServer, tmp_path: Path
) -> None:
    url = server.base_url(site) + "team.html"
    with contract.WalkBrowser(headless=True, profile_dir=tmp_path / "profile") as wb:
        page = wb.goto(url)
        assert page.url == url and "Pekka Salo" in page.text and "<html" in page.html
        kinds = {(c.kind, c.text) for c in page.candidates}
        assert ("button", "Näytä yhteystiedot") in kinds and ("link", "Seuraava sivu") in kinds
        assert not any(
            c.href.startswith("mailto:") or c.href.startswith("tel:") for c in page.candidates
        )
        button = next(c for c in page.candidates if c.kind == "button")
        after = wb.click(button)
        assert "pekka.salo@fixture.example" in after.text and "mailto:pekka.salo" in after.html
        assert not any(c.text == "Näytä yhteystiedot" for c in after.candidates)
        scrolled = wb.scroll()
        assert scrolled.url == after.url
