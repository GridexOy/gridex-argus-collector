"""Shared fixtures for the walk integration tests: the fixture site, gold data."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from argus_collector.models.contract import ModelConfig
from argus_collector.walk import contract
from collector.tests.fake_model_server import FakeModelServer
from test_site import server

GOLD = Path(__file__).resolve().parents[5] / "test_site" / "gold" / "fixture_oy.json"


@pytest.fixture(scope="module")
def site() -> Iterator[str]:
    srv = server.start(port=0)
    try:
        yield server.base_url(srv)
    finally:
        srv.shutdown()
        srv.server_close()


@pytest.fixture
def gold() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(GOLD.read_text(encoding="utf-8"))
    return data


def settings_for(
    site: str, fake: FakeModelServer, tmp_path: Path, budget: int = 10,
    stop_at_goal: bool = False,  # these walks read the whole site (gold); goal: test_goal
) -> contract.WalkSettings:
    return contract.WalkSettings(
        start_url=site,
        model=ModelConfig(fake.endpoint, "fake-instruct"),
        page_budget=budget,
        headless=True,
        profile_dir=tmp_path / "profile",
        evidence_dir=tmp_path / "evidence",
        db_path=tmp_path / "collector.db",
        stop_files=(tmp_path / "STOP",),
        stop_at_goal=stop_at_goal,
    )
