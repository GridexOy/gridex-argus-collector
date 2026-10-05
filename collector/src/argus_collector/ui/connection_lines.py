"""Pure props of the Yhteys block: the pairing key field, Yhdistä, Yhdistä uudelleen
(TZ_TANDEM A1; owner 05.10.2026: a slow answer is Hidas yhteys, not Ei verkkoa)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from argus_collector.api_client import contract as api
from argus_collector.delivery import contract as delivery
from argus_collector.ui.repository import Messages
from argus_collector.worker_auth import contract as worker_auth

LEVEL_OK = "ok"
LEVEL_WARN = "warn"
LEVEL_ERROR = "error"

STATE_NONE = "none"
STATE_CHECKING = "checking"
STATE_OK = "ok"
STATE_REJECTED = "rejected"
STATE_ERROR = "error"
STATE_SLOW = "slow"  # no answer within the read time-out: the network is there, ARGUS is slow
STATE_PANEL = "panel"  # a fault inside the panel while sending a heartbeat

KEY_ERRORS = {
    worker_auth.REASON_FORMAT: "connection.key.format",
    worker_auth.REASON_MISSING: "connection.key.missing",
    worker_auth.REASON_DUPLICATE: "connection.key.duplicate",
    worker_auth.REASON_CHARACTERS: "connection.key.characters",
    worker_auth.REASON_URL: "connection.key.url",
    worker_auth.REASON_HTTPS: "connection.key.https",
}


@dataclass(frozen=True)
class ConnectionState:
    """What `app_connection.ConnectionController` knows right now."""

    address: str
    worker_id: str
    token: str  # masked
    status: str = STATE_NONE
    error_detail: str = ""
    error_status: int = 0  # HTTP status of the failed heartbeat (0: no answer at all)
    slow_s: int = 0  # seconds the slow heartbeat waited
    last_heartbeat: datetime | None = None
    testing: bool = False
    key_error: worker_auth.PairingKeyError | None = None  # the last pasted key was refused


@dataclass(frozen=True)
class ConnectionProps:
    title: str
    key_label: str
    connect_label: str
    reconnect_label: str
    paired_text: str
    key_error_text: str  # "" when the last key was fine
    state_text: str
    state_level: str
    heartbeat_text: str
    connect_enabled: bool
    reconnect_enabled: bool  # a saved pairing and no heartbeat being checked


def _state_line(msgs: Messages, state: ConnectionState) -> tuple[str, str]:
    if state.status == STATE_OK:
        return msgs.t("connection.state.ok"), LEVEL_OK
    if state.status == STATE_REJECTED:
        return msgs.t("connection.state.rejected"), LEVEL_ERROR
    if state.status == STATE_SLOW:
        return msgs.t("connection.state.slow", s=state.slow_s), LEVEL_WARN
    if state.status == STATE_PANEL:
        return msgs.t("connection.state.panel", detail=state.error_detail), LEVEL_ERROR
    if state.status == STATE_ERROR and state.error_status >= 500:
        return msgs.t("delivery.serverError", status=state.error_status), LEVEL_ERROR
    if state.status == STATE_ERROR and state.error_status:
        detail = state.error_detail or msgs.t("delivery.rejected.http", status=state.error_status)
        return msgs.t("connection.state.refused", status=state.error_status,
                      detail=detail), LEVEL_ERROR
    if state.status == STATE_ERROR:
        return msgs.t("connection.state.error", detail=state.error_detail), LEVEL_ERROR
    if state.status == STATE_CHECKING:
        return msgs.t("connection.state.checking"), LEVEL_WARN
    return msgs.t("connection.state.disconnected"), LEVEL_WARN


def _heartbeat_text(msgs: Messages, state: ConnectionState) -> str:
    if state.last_heartbeat is None:
        return msgs.t("connection.heartbeat.never")
    stamp = state.last_heartbeat.strftime("%H:%M:%S")
    return msgs.t("connection.heartbeat.at", time=stamp)


def _paired_text(msgs: Messages, state: ConnectionState) -> str:
    if not state.address or not state.worker_id:
        return msgs.t("connection.unpaired")
    return msgs.t("connection.paired", address=state.address, worker=state.worker_id,
                  token=state.token)


def key_error_text(msgs: Messages, error: worker_auth.PairingKeyError | None) -> str:
    if error is None:
        return ""
    key = KEY_ERRORS.get(error.reason, "connection.key.format")
    return msgs.t(key, field=error.field)


def connection_props(msgs: Messages, state: ConnectionState) -> ConnectionProps:
    state_text, state_level = _state_line(msgs, state)
    return ConnectionProps(
        title=msgs.t("connection.title"),
        key_label=msgs.t("connection.keyLabel"),
        connect_label=msgs.t("connection.connect"),
        reconnect_label=msgs.t("connection.reconnect"),
        paired_text=_paired_text(msgs, state),
        key_error_text=key_error_text(msgs, state.key_error),
        state_text=state_text,
        state_level=state_level,
        heartbeat_text=_heartbeat_text(msgs, state),
        connect_enabled=not state.testing,
        reconnect_enabled=bool(state.address and state.worker_id) and not state.testing,
    )


def timed_out(exc: api.ApiError, elapsed_s: float) -> int:
    """Seconds waited when a heartbeat got no answer within its time-out (the socket says
    `timed out`), else 0. A refused connection is no answer at all, however long Windows
    takes to say so (about 2 s on MAIN-PC, 0.4.8.3)."""
    if exc.status == 0 and "timed out" in exc.raw.lower():
        return max(1, round(elapsed_s))
    return 0


def heartbeat_line(status: int, body: api.Error | None, slow_s: int = 0) -> str:
    """`heartbeat: HTTP 502 http_502 (server error 502)`, ARGUS's request_id when sent."""
    if status == 200:
        return "heartbeat: HTTP 200 answered"
    if slow_s:
        return f"heartbeat: no answer in {slow_s} s (slow, not offline)"
    code = body.code if body else f"http_{status}" if status else "offline"
    rid = f" request_id={body.request_id}" if body and body.request_id else ""
    return f"heartbeat: HTTP {status} {code} ({delivery.reason(code)}){rid}"
