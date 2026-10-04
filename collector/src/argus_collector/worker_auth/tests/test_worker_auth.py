"""worker_auth: masking, connection round-trip, token round-trip (both platforms)."""

from __future__ import annotations

from pathlib import Path

import pytest

from argus_collector.worker_auth import contract, repository, service


def test_mask_token_keeps_only_last_four() -> None:
    assert service.mask_token("abc123secret") == "********cret"
    assert service.mask_token("ab") == "**"
    assert service.mask_token("") == ""


def test_connection_round_trip(tmp_path: Path) -> None:
    repository.save_connection_mapping(
        {"base_url": "https://argus.gridex.fi", "worker_id": "worker-main-pc"}, tmp_path
    )
    mapping = repository.load_connection_mapping(tmp_path)
    assert mapping is not None
    connection = service.connection_from_mapping(mapping)
    assert connection == service.SavedConnection("https://argus.gridex.fi", "worker-main-pc")


def test_connection_missing_file_returns_none(tmp_path: Path) -> None:
    assert repository.load_connection_mapping(tmp_path) is None


def test_connection_from_mapping_rejects_bad_shapes() -> None:
    assert service.connection_from_mapping({}) is None
    assert service.connection_from_mapping({"base_url": "x"}) is None
    assert service.connection_from_mapping({"base_url": "", "worker_id": "w"}) is None


def test_token_round_trip_off_windows(tmp_path: Path) -> None:
    repository.save_token("test-token-abc", tmp_path, windows=False)
    assert repository.load_token(tmp_path, windows=False) == "test-token-abc"


def test_token_missing_file_returns_none(tmp_path: Path) -> None:
    assert repository.load_token(tmp_path, windows=False) is None


def test_clear_token_removes_file(tmp_path: Path) -> None:
    repository.save_token("x", tmp_path, windows=False)
    repository.clear_token(tmp_path)
    assert repository.load_token(tmp_path, windows=False) is None
    repository.clear_token(tmp_path)  # idempotent, no error on a missing file


def test_contract_save_and_load_connection(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ARGUS_COLLECTOR_HOME", str(tmp_path))
    contract.save_connection("https://argus.gridex.fi", "worker-main-pc")
    loaded = contract.load_connection()
    assert loaded == contract.SavedConnection("https://argus.gridex.fi", "worker-main-pc")


def test_contract_save_and_load_token(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """On Windows this exercises real DPAPI; off Windows, the XOR fallback."""
    monkeypatch.setenv("ARGUS_COLLECTOR_HOME", str(tmp_path))
    assert contract.load_token() is None
    contract.save_token("test-token-abc")
    assert contract.load_token() == "test-token-abc"
    assert (tmp_path / repository.TOKEN_FILE).read_bytes() != b"test-token-abc"
    contract.clear_token()
    assert contract.load_token() is None
