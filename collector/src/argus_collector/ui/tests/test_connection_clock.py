"""Yhteys on the heartbeat clock (owner 05.10.2026, 0.4.8.2): a slow ARGUS is Hidas yhteys and
the clock goes on; a rejected token and a fault in the panel do not stop it either; Yhdista
uudelleen sends at once; an empty key field says nothing."""

from __future__ import annotations

import sqlite3
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from argus_collector.api_client import contract as api
from argus_collector.diagnostics import contract as diagnostics
from argus_collector.runtime import contract as runtime
from argus_collector.scheduler import contract as scheduler
from argus_collector.ui import app_connection, heartbeat_loop
from argus_collector.ui.app_connection import ConnectionController
from argus_collector.ui.connection_lines import (
    STATE_ERROR,
    STATE_OK,
    STATE_PANEL,
    STATE_REJECTED,
    STATE_SLOW,
)
from argus_collector.ui.repository import load_messages
from argus_collector.ui.tests.slow_argus import SlowArgus
from contract_server import server as contract_server

TOKEN, WORKER = "test-token-abc", "worker-main-pc"


class FakeHost:
    def __init__(self) -> None:
        self.config = runtime.Config(network_proxy="direct")
        self.report: diagnostics.Report | None = None
        self.failed: list[int] = []
        self.fail_fields = 0

    def post(self, action: Callable[[], None]) -> None:
        action()

    def refresh(self) -> None:
        return None

    def heartbeat_fields(self) -> scheduler.HeartbeatFields:
        if self.fail_fields:
            self.fail_fields -= 1
            raise sqlite3.OperationalError("database is locked")
        return scheduler.HeartbeatFields(False, [], 0, 1, [])

    def heartbeat_answered(self, response: api.HeartbeatResponse, acks: list[str]) -> None:
        return None

    def heartbeat_failed(self, status: int) -> None:
        self.failed.append(status)

    def connection_ok(self) -> None:
        return None


def wait_for(predicate: Callable[[], bool], timeout_s: float = 10.0,
             seen: Callable[[], object] = lambda: "") -> float:
    """Seconds until `predicate` held; on a time-out the assertion shows `seen()`."""
    started = time.monotonic()
    while not predicate() and time.monotonic() < started + timeout_s:
        time.sleep(0.02)
    waited = time.monotonic() - started
    assert predicate(), f"not after {waited:.1f} s: {seen()}"
    return waited


@pytest.fixture
def stand(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[SlowArgus]:
    monkeypatch.setenv("ARGUS_COLLECTOR_HOME", str(tmp_path))
    monkeypatch.setattr(heartbeat_loop, "HEARTBEAT_INTERVAL_S", 0.3)
    monkeypatch.setattr(heartbeat_loop, "HEARTBEAT_TIMEOUT_S", 1.0)
    argus = contract_server.start(port=0, tokens={TOKEN: WORKER})
    slow = SlowArgus(contract_server.base_url(argus)).start()
    try:
        yield slow
    finally:
        slow.stop()
        argus.shutdown()
        argus.server_close()


def paired(stand: SlowArgus, host: FakeHost, token: str = TOKEN) -> ConnectionController:
    ctl = ConnectionController(host)
    ctl.pair(contract_server.pairing_key(stand.address, WORKER, token))
    return ctl


def test_a_slow_argus_is_hidas_yhteys_and_the_clock_goes_on(stand: SlowArgus) -> None:
    host = FakeHost()
    stand.delay_s = 1.5
    ctl = paired(stand, host)
    wait_for(lambda: ctl.state.status == STATE_SLOW)
    assert ctl.props(load_messages()).state_text == f"Hidas yhteys: {ctl.state.slow_s} s"
    assert ctl.state.slow_s >= 1 and host.failed == [], "slow is not Ei verkkoa in Lahetys"
    stand.delay_s = 0.0
    wait_for(lambda: ctl.state.status == STATE_OK)
    first = ctl.state.last_heartbeat
    wait_for(lambda: ctl.state.last_heartbeat != first)
    ctl.loop.stop()


def test_a_rejected_token_and_a_panel_fault_do_not_stop_the_clock(stand: SlowArgus) -> None:
    host = FakeHost()
    ctl = paired(stand, host, "not-a-real-token")
    wait_for(lambda: ctl.state.status == STATE_REJECTED)
    seen = stand.heartbeats
    wait_for(lambda: stand.heartbeats >= seen + 2)
    ctl.loop.stop()
    host = FakeHost()
    host.fail_fields = 1
    ctl = paired(stand, host)
    wait_for(lambda: ctl.state.status == STATE_PANEL)
    text = ctl.props(load_messages()).state_text
    assert text == "Paneelin virhe: OperationalError: database is locked"
    wait_for(lambda: ctl.state.status == STATE_OK)
    ctl.loop.stop()


def test_no_answer_at_all_is_ei_verkkoa(
    stand: SlowArgus, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Windows refuses a closed localhost port only after ~2 s (TCP re-sends the SYN),
    so the read time-out here is 10 s, as in the panel it is 30 s (MAIN-PC, 0.4.8.4)."""
    monkeypatch.setattr(heartbeat_loop, "HEARTBEAT_TIMEOUT_S", 10.0)
    host = FakeHost()
    ctl = ConnectionController(host)
    ctl.pair(contract_server.pairing_key("http://127.0.0.1:9", WORKER, TOKEN))
    waited = wait_for(lambda: ctl.state.status == STATE_ERROR, timeout_s=30.0,
                      seen=lambda: (ctl.state.status, ctl.state.slow_s, ctl.state.error_detail))
    print(f"refused port answered as Ei verkkoa after {waited:.1f} s")
    assert ctl.props(load_messages()).state_text.startswith("Ei verkkoa: ")
    assert host.failed and host.failed[0] == 0
    ctl.loop.stop()


def test_reconnect_sends_at_once_and_an_empty_key_says_nothing(
    stand: SlowArgus, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(heartbeat_loop, "HEARTBEAT_INTERVAL_S", 30.0)
    host = FakeHost()
    ctl = ConnectionController(host)
    assert not ctl.props(load_messages()).reconnect_enabled, "nothing saved yet"
    ctl.pair("   ")
    assert ctl.state.key_error is None and stand.heartbeats == 0
    ctl.pair("argus://pair?url=x")
    assert ctl.state.key_error is not None, "a non-empty bad key is refused"
    ctl.pair(contract_server.pairing_key(stand.address, WORKER, TOKEN))
    wait_for(lambda: ctl.state.status == STATE_OK)
    assert ctl.state.key_error is None
    assert ctl.props(load_messages()).reconnect_enabled
    ctl.reconnect()
    wait_for(lambda: stand.heartbeats == 2, timeout_s=3.0)
    ctl.loop.stop()


def test_an_attempt_stuck_in_the_panel_shows_as_hidas_yhteys(
    stand: SlowArgus, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(heartbeat_loop, "HEARTBEAT_TIMEOUT_S", 0.2)
    monkeypatch.setattr(app_connection, "STUCK_GRACE_S", 0.1)
    release = threading.Event()
    host = FakeHost()
    ctl = paired(stand, host)
    wait_for(lambda: ctl.state.status == STATE_OK)
    answer = host.heartbeat_fields

    def stuck() -> scheduler.HeartbeatFields:
        release.wait(5)
        return answer()

    monkeypatch.setattr(host, "heartbeat_fields", stuck)
    ctl.reconnect()
    time.sleep(0.5)
    ctl.watch()
    assert ctl.state.status == STATE_SLOW, "the panel says it waits, not that all is well"
    assert ctl.props(load_messages()).state_text.startswith("Hidas yhteys: ")
    release.set()
    wait_for(lambda: ctl.state.status == STATE_OK)
    ctl.loop.stop()
