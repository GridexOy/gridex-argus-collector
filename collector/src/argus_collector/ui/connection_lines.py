"""Pure props of the Yhteys block (ARGUS20_TZ_TANDEM.md pair A1)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from argus_collector.ui.repository import Messages

LEVEL_OK = "ok"
LEVEL_WARN = "warn"
LEVEL_ERROR = "error"

STATE_NONE = "none"
STATE_CHECKING = "checking"
STATE_OK = "ok"
STATE_REJECTED = "rejected"
STATE_ERROR = "error"


@dataclass(frozen=True)
class ConnectionState:
    """What `app_connection.ConnectionController` knows right now."""

    address: str
    worker_id: str
    token: str
    status: str = STATE_NONE
    error_detail: str = ""
    last_heartbeat: datetime | None = None
    testing: bool = False


@dataclass(frozen=True)
class ConnectionProps:
    title: str
    address_label: str
    worker_id_label: str
    token_label: str
    test_label: str
    address_value: str
    worker_id_value: str
    token_display: str
    state_text: str
    state_level: str
    heartbeat_text: str
    test_enabled: bool


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


def connection_props(msgs: Messages, state: ConnectionState) -> ConnectionProps:
    state_text, state_level = _state_line(msgs, state)
    return ConnectionProps(
        title=msgs.t("connection.title"),
        address_label=msgs.t("connection.addressLabel"),
        worker_id_label=msgs.t("connection.workerIdLabel"),
        token_label=msgs.t("connection.tokenLabel"),
        test_label=msgs.t("connection.test"),
        address_value=state.address,
        worker_id_value=state.worker_id,
        token_display=state.token,
        state_text=state_text,
        state_level=state_level,
        heartbeat_text=_heartbeat_text(msgs, state),
        test_enabled=not state.testing,
    )
