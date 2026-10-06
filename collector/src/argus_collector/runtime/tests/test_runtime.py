"""Unit tests for the runtime module (paths, version line, kill switch)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from argus_collector.runtime import contract, repository, service


def test_repo_root_holds_version_file() -> None:
    assert (contract.repo_root() / "VERSION").is_file()


def test_user_data_dir_honours_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(repository.HOME_ENV, str(tmp_path))
    assert contract.user_data_dir() == tmp_path
    assert contract.browser_profile_dir() == tmp_path / "browser-profile"


def test_user_data_dir_default_ends_with_vendor_app(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(repository.HOME_ENV, raising=False)
    path = contract.user_data_dir()
    assert path.parts[-2:] == ("Gridex", "ArgusCollector")


@pytest.mark.parametrize("text", ["0.0.1.0", "0.3.2.1", "0.12.4.10"])
def test_validate_version_accepts_stage_step_fix(text: str) -> None:
    assert service.validate_version(text) is None


@pytest.mark.parametrize("text", ["1.0.0.0", "0.0.1", "v0.0.1.0", "0.0.1.0-rc", ""])
def test_validate_version_rejects_other_shapes(text: str) -> None:
    assert service.validate_version(text) is not None


def test_finnish_stamp_has_no_leading_zero_in_day_and_month() -> None:
    assert service.finnish_stamp(datetime(2026, 10, 3, 14, 32)) == "3.10.2026 klo 14.32"
    assert service.finnish_stamp(datetime(2026, 1, 9, 8, 5)) == "9.1.2026 klo 8.05"


def test_version_line_with_build() -> None:
    raw = {"version": "0.0.1.0", "commit": "abc1234def", "built_at": "2026-10-03T14:32:05+03:00"}
    status = service.version_status("0.0.1.0", raw)
    assert status.error is None
    stamp = (
        service.finnish_stamp(status.build.built_at)
        if status.build and status.build.built_at
        else ""
    )
    assert service.version_line(status, stamp) == "cv0.0.1.0 (3.10.2026 klo 14.32) abc1234"


def test_version_line_without_build_shows_not_installed_text() -> None:
    status = service.version_status("0.0.1.0", None)
    assert service.version_line(status, "ei asennustietoa") == "cv0.0.1.0 (ei asennustietoa)"


def test_version_mismatch_is_an_error() -> None:
    raw = {"version": "0.0.0.0", "commit": "abc1234", "built_at": "2026-10-03T14:32:05"}
    status = service.version_status("0.0.1.0", raw)
    assert status.error is not None
    assert "0.0.0.0" in status.error and "0.0.1.0" in status.error


def test_read_build_file_rejects_non_object(tmp_path: Path) -> None:
    (tmp_path / repository.BUILD_FILE).write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(ValueError):
        repository.read_build_file(tmp_path)


def test_read_build_file_accepts_bom(tmp_path: Path) -> None:
    payload = {"version": "0.0.1.0", "commit": "abc", "built_at": "2026-10-03T10:00:00"}
    (tmp_path / repository.BUILD_FILE).write_bytes(b"\xef\xbb\xbf" + json.dumps(payload).encode())
    assert repository.read_build_file(tmp_path) == payload


def test_stop_files_detected_in_both_places(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    data = tmp_path / "data"
    root.mkdir()
    data.mkdir()
    assert repository.existing_stop_files(root, data) == []
    (data / "STOP").write_text("", encoding="utf-8")
    assert repository.existing_stop_files(root, data) == [data / "STOP"]
    (root / "STOP").write_text("", encoding="utf-8")
    found = repository.existing_stop_files(root, data)
    assert found == [root / "STOP", data / "STOP"]
    assert service.describe_stop(found) == f"{root / 'STOP'}, {data / 'STOP'}"
    assert service.describe_stop([]) is None


def test_config_defaults_and_mapping() -> None:
    assert service.config_from_mapping({}, "defaults").test_site_port == 8765
    cfg = service.config_from_mapping(
        {
            "model": {"endpoint": "http://127.0.0.1:9000", "name": "llama3.1:8b"},
            "test_site": {"port": 9001},
            "walk": {"page_budget": 3},
        },
        "x",
    )
    assert cfg.model_endpoint == "http://127.0.0.1:9000" and cfg.test_site_port == 9001
    assert cfg.model_name == "llama3.1:8b" and cfg.walk_page_budget == 3
    assert service.config_from_mapping({}, "d").model_name == ""


def test_config_routed_models_default_and_can_be_switched_off() -> None:
    cfg = service.config_from_mapping({}, "d")
    assert (cfg.model_navigation, cfg.model_vision) == ("qwen2.5:7b", "qwen2.5-vl:7b")
    off = service.config_from_mapping({"model": {"navigation": "", "vision": ""}}, "x")
    assert (off.model_navigation, off.model_vision) == ("", "")


def test_config_rejects_bad_page_budget() -> None:
    with pytest.raises(ValueError):
        service.config_from_mapping({"walk": {"page_budget": 0}}, "x")


@pytest.mark.parametrize("port", [0, 70000, "8765", True])
def test_config_rejects_bad_port(port: object) -> None:
    with pytest.raises(ValueError):
        service.config_from_mapping({"test_site": {"port": port}}, "x")


def test_read_config_file_rejects_list(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("- a\n- b\n", encoding="utf-8")
    with pytest.raises(ValueError):
        repository.read_config_file(path)
    path.write_text("", encoding="utf-8")
    assert repository.read_config_file(path) == {}


def test_load_config_prefers_user_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(repository.HOME_ENV, str(tmp_path))
    (tmp_path / "config.yaml").write_text("test_site:\n  port: 9100\n", encoding="utf-8")
    cfg = contract.load_config()
    assert cfg.test_site_port == 9100 and cfg.source == str(tmp_path / "config.yaml")


def test_walk_settings_of_the_config_file() -> None:
    """walk.action_budget (0.4.8.6) and walk.stop_at_goal (owner 06.10.2026)."""
    parsed = service.config_from_mapping({"walk": {"action_budget": 25, "stop_at_goal": False}},
                                         "test")
    assert (parsed.walk_action_budget, parsed.walk_stop_at_goal) == (25, False)
    assert service.Config().walk_stop_at_goal is True
    with pytest.raises(ValueError, match="stop_at_goal"):
        service.config_from_mapping({"walk": {"stop_at_goal": "no"}}, "test")
