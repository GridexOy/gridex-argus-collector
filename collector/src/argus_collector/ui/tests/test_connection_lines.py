"""Yhteys lines: a 5xx is Palvelinvirhe, a 4xx names ARGUS's answer; the heartbeat journal."""

from __future__ import annotations

from dataclasses import replace

from argus_collector.api_client import contract as api
from argus_collector.ui.connection_lines import (
    STATE_ERROR,
    ConnectionState,
    connection_props,
    heartbeat_line,
)
from argus_collector.ui.repository import load_messages


def test_heartbeat_line_words_and_request_id() -> None:
    body = api.Error("lease_mismatch", "detail", False, "req-9")
    assert heartbeat_line(200, None) == "heartbeat: HTTP 200 answered"
    assert heartbeat_line(502, None) == "heartbeat: HTTP 502 http_502 (server error 502)"
    assert heartbeat_line(409, body) == (
        "heartbeat: HTTP 409 lease_mismatch (the lease does not match) request_id=req-9")


def test_a_server_error_is_palvelinvirhe_not_ei_verkkoa() -> None:
    msgs = load_messages()
    base = ConnectionState("https://argus.example", "w", "****", STATE_ERROR)
    proxy_page = connection_props(msgs, replace(base, error_status=502))
    assert proxy_page.state_text == "Palvelinvirhe: 502", "no raw html, no 'Ei verkkoa'"
    refused = connection_props(msgs, replace(base, error_status=403, error_detail="revoked"))
    assert refused.state_text == "ARGUS vastasi 403: revoked"
    bare = connection_props(msgs, replace(base, error_status=404))
    assert bare.state_text == "ARGUS vastasi 404: HTTP-virhe 404 ilman syytä"
    down = connection_props(msgs, replace(base, error_detail="HTTP 0: refused"))
    assert down.state_text == "Ei verkkoa: HTTP 0: refused"
