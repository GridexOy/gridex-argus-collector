"""Pure props of the Yhteys block: one pairing key field and Yhdistä (TZ_TANDEM A1)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

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
    last_heartbeat: datetime | None = None
    testing: bool = False
    key_error: worker_auth.PairingKeyError | None = None  # the last pasted key was refused


@dataclass(frozen=True)
class ConnectionProps:
    title: str
    key_label: str
    connect_label: str
    paired_text: str
    key_error_text: str  # "" when the last key was fine
    state_text: str
    state_level: str
    heartbeat_text: str
    connect_enabled: bool


def _state_line(msgs: Messages, state: ConnectionState) -> tuple[str, str]:
    if state.status == STATE_OK:
        return msgs.t("connection.state.ok"), LEVEL_OK
    if state.status == STATE_REJECTED:
        return msgs.t("connection.state.rejected"), LEVEL_ERROR
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
        paired_text=_paired_text(msgs, state),
        key_error_text=key_error_text(msgs, state.key_error),
        state_text=state_text,
        state_level=state_level,
        heartbeat_text=_heartbeat_text(msgs, state),
        connect_enabled=not state.testing,
    )
