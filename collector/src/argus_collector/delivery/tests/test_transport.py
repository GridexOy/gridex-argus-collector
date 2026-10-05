"""One transport state (owner 05.10.2026, 0.4.8.2): Ei verkkoa only when neither the heartbeat
nor delivery got an answer; Yhdistetty with Lahetys Ei verkkoa cannot happen."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import pytest

from argus_collector.api_client import contract as api
from argus_collector.delivery import contract as delivery
from argus_collector.delivery.hooks import Failed
from argus_collector.delivery.tests.test_link import TARGET, NoJobs
from argus_collector.storage import contract as storage


@pytest.fixture
def deliverer(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> delivery.Deliverer:
    monkeypatch.setenv("ARGUS_COLLECTOR_HOME", str(tmp_path / "home"))
    found = delivery.Deliverer(tmp_path / "c.sqlite3", lambda: TARGET, NoJobs())
    conn = storage.connect(tmp_path / "c.sqlite3")
    try:
        found.tick(conn)  # paired, nothing to send
    finally:
        conn.close()
    found.pending = 5
    return found


def no_answer(found: delivery.Deliverer) -> None:
    with pytest.raises(Failed):
        found._api_error(api.ApiError(0, None, None, "timed out"), "j1", "r1", "t")


def test_a_delivery_request_without_answer_alone_is_not_offline(
    deliverer: delivery.Deliverer,
) -> None:
    deliverer.link(True)
    no_answer(deliverer)
    assert deliverer.state == "syncing", "heartbeat passes: Lahetetaan, a retry follows"


def test_delivery_answers_while_the_heartbeat_has_none_is_not_offline(
    deliverer: delivery.Deliverer,
) -> None:
    deliverer.link(False)
    assert deliverer.state == "offline", "heartbeat down, delivery has not answered since"
    time.sleep(0.01)
    deliverer.transport.answered()  # an events request got its answer: the queue goes down
    assert deliverer.state == "syncing"


def test_both_without_answer_is_offline_and_any_answer_ends_it(
    deliverer: delivery.Deliverer,
) -> None:
    deliverer.link(False)
    no_answer(deliverer)
    assert deliverer.state == "offline"
    time.sleep(0.01)
    with pytest.raises(Failed):  # a 502 is an answer: the link is there, ARGUS is not well
        deliverer._api_error(api.ApiError(502, None, None, "<html>"), "j1", "r1", "t")
    assert deliverer.state == "syncing"
    deliverer.link(False)
    assert deliverer.state == "syncing", "heartbeat still down, delivery answered last"
    no_answer(deliverer)
    assert deliverer.state == "offline", "then delivery got no answer either"


def test_not_paired_is_offline(tmp_path: Path) -> None:
    found = delivery.Deliverer(tmp_path / "c.sqlite3", lambda: None, NoJobs())
    conn: sqlite3.Connection = storage.connect(tmp_path / "c.sqlite3")
    try:
        found.tick(conn)
    finally:
        conn.close()
    assert found.state == "offline"
