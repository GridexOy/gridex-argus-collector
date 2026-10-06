"""WINLOG 06.10.2026: claim waited 10 s and failed 69 % of the time while the heartbeat
(30 s) kept Yhteys green; every ARGUS call of the collector now waits 30 s."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from argus_collector.api_client import contract as api
from argus_collector.delivery import contract as delivery
from argus_collector.scheduler.tests.stands import make_collector
from argus_collector.storage import contract as storage
from contract_server import server as contract_server


def test_claim_waits_as_long_as_the_heartbeat(
    tmp_path: Path, argus: contract_server.ContractServer, monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[float] = []

    def claim(*args: Any, **kwargs: Any) -> api.ClaimResponse:
        seen.append(kwargs["timeout_s"])
        raise api.ApiError(0, None, None, "no answer")

    monkeypatch.setattr(api, "claim_jobs", claim)
    collector = make_collector(tmp_path, argus, "http://127.0.0.1:9/v1")
    conn = storage.connect(tmp_path / "collector.db")
    try:
        target = collector.target()
        assert target is not None
        collector._claim(conn, target)
    finally:
        conn.close()
    assert seen == [30.0] and delivery.API_TIMEOUT_S == 30.0
    assert collector.queue_view().claim_state == "failed", "Jono says so"
