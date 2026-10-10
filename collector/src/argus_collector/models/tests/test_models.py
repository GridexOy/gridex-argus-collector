"""Model adapter against the fake OpenAI-compatible server (test double)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from argus_collector.models import contract, repository, service
from argus_collector.storage import contract as storage
from collector.tests.fake_model_server import FakeModelServer


@pytest.fixture
def server() -> Iterator[FakeModelServer]:
    srv = FakeModelServer(lambda system, user: '{"echo": "' + user[:5] + '"}').start()
    try:
        yield srv
    finally:
        srv.stop()


def test_health_lists_model(server: FakeModelServer) -> None:
    ok = contract.health(server.endpoint, "fake-instruct")
    assert ok.reachable and ok.model_listed
    missing = contract.health(server.endpoint, "other-model")
    assert missing.reachable and not missing.model_listed and "not listed" in missing.detail
    down = contract.health("http://127.0.0.1:9/v1", "fake-instruct")
    assert not down.reachable and "no answer" in down.detail


def test_health_accepts_latest_tag() -> None:
    assert service.health_from_models(["qwen2.5:14b-instruct:latest"], "qwen2.5:14b-instruct")
    assert service.health_from_models(["llama3.1:8b"], "qwen2.5:14b-instruct").model_listed is False


def test_chat_json_logs_tokens_and_zero_cost(server: FakeModelServer, tmp_path: Path) -> None:
    conn = storage.connect(tmp_path / "c.db")
    client = contract.ModelClient(contract.ModelConfig(server.endpoint, "fake-instruct"), conn)
    data = client.chat_json("sys", "hello world", "test_purpose")
    assert data == {"echo": "hello"}
    body = server.requests[-1]
    assert body["model"] == "fake-instruct"
    assert body["response_format"] == {"type": "json_object"}
    assert body["temperature"] == 0.0
    row = conn.execute("SELECT * FROM model_calls").fetchone()
    assert row["provider"] == "local" and row["model"] == "fake-instruct"
    assert row["purpose"] == "test_purpose" and row["cost_eur"] == 0 and row["ok"] == 1
    assert row["prompt_tokens"] == 2 and row["completion_tokens"] >= 1
    assert repository.call_totals(conn)["calls"] == 1


def test_http_error_is_logged_and_raised(server: FakeModelServer, tmp_path: Path) -> None:
    conn = storage.connect(tmp_path / "c.db")
    client = contract.ModelClient(contract.ModelConfig(server.endpoint, "fake-instruct"), conn)
    server.fail_next = 1
    with pytest.raises(contract.ModelError, match="HTTP 500"):
        client.chat("sys", "x", "p")
    row = conn.execute("SELECT ok, error FROM model_calls").fetchone()
    assert row["ok"] == 0 and "HTTP 500" in row["error"]


def test_bad_json_is_one_attempt_then_error(tmp_path: Path) -> None:
    srv = FakeModelServer(lambda s, u: "not json at all").start()
    try:
        conn = storage.connect(tmp_path / "c.db")
        client = contract.ModelClient(contract.ModelConfig(srv.endpoint, "fake-instruct"), conn)
        with pytest.raises(contract.ModelError, match="JSON"):
            client.chat_json("sys", "x", "cards")
        purposes = [r["purpose"] for r in conn.execute("SELECT purpose FROM model_calls")]
        assert purposes == ["cards"], "6.1: one attempt, no retry of the same window"
    finally:
        srv.stop()


def test_parse_json_reply_tolerates_fences_and_prose() -> None:
    assert service.parse_json_reply('```json\n{"a": 1}\n```') == {"a": 1}
    assert service.parse_json_reply('Sure: {"a": {"b": 2}} done') == {"a": {"b": 2}}
    assert service.parse_json_reply("[1, 2]") is None
    assert service.parse_json_reply("") is None


def _has_proxy_handler(opener: object) -> bool:
    import urllib.request

    handlers: list[object] = getattr(opener, "handlers", [])
    return any(isinstance(h, urllib.request.ProxyHandler) for h in handlers)


def test_direct_opener_has_no_proxy_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    import urllib.request

    monkeypatch.setenv("HTTP_PROXY", "http://proxy.invalid:3128")
    monkeypatch.setenv("http_proxy", "http://proxy.invalid:3128")
    assert _has_proxy_handler(urllib.request.build_opener())
    assert not _has_proxy_handler(urllib.request.build_opener(urllib.request.ProxyHandler({})))
    assert not _has_proxy_handler(repository.DIRECT_OPENER)


def test_listener_hears_every_call_success_and_failure(server: FakeModelServer) -> None:
    heard: list[contract.CallRecord] = []
    client = contract.ModelClient(
        contract.ModelConfig(server.endpoint, "fake-instruct"), None, heard.append
    )
    client.chat_json("sys", "hello world", "walk.cards")
    server.fail_next = 1
    with pytest.raises(contract.ModelError):
        client.chat("sys", "x", "walk.action")
    assert [(r.purpose, r.ok) for r in heard] == [("walk.cards", True), ("walk.action", False)]
    assert heard[0].model == "fake-instruct" and heard[0].prompt_tokens == 2
    assert heard[0].started_at.endswith("+00:00") and "HTTP 500" in heard[1].error
