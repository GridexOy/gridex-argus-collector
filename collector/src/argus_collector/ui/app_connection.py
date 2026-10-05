"""Yhteys controller: pairing key, Yhdistä, Yhdistä uudelleen, heartbeats (TZ_TANDEM A1).

Yhdistä parses the pasted `argus://pair?...` key, saves it (address and
worker_id plain, token with DPAPI) and sends a heartbeat at once; an empty
field does nothing. A saved key connects by itself at every panel start;
Yhdistä uudelleen sends a heartbeat with it at once, no key needed.
Heartbeats (owner 05.10.2026, `heartbeat_loop`): every 30 s whatever the last
answer was (a rejected token included), 30 s read time-out; a time-out shows
`Hidas yhteys: N s` (not `Ei verkkoa`, which is for no answer at all). Lähetys
is `Ei verkkoa` only when Yhteys is and delivery got no answer either
(`delivery.Transport`).
"""

from __future__ import annotations

import functools
import time
from dataclasses import replace
from datetime import UTC, datetime
from typing import cast

from argus_collector.api_client import contract as api
from argus_collector.delivery import contract as delivery
from argus_collector.runtime import contract as runtime
from argus_collector.ui import heartbeat_call, heartbeat_loop
from argus_collector.ui.connection_lines import (
    STATE_CHECKING,
    STATE_ERROR,
    STATE_OK,
    STATE_PANEL,
    STATE_REJECTED,
    STATE_SLOW,
    ConnectionProps,
    ConnectionState,
    heartbeat_line,
    timed_out,
)
from argus_collector.ui.connection_lines import connection_props as build_connection_props
from argus_collector.ui.repository import Messages
from argus_collector.worker_auth import contract as worker_auth

STUCK_GRACE_S = 5.0  # an attempt longer than its time-out + this is stuck in the panel


class ConnectionController:
    def __init__(self, host: heartbeat_call.Host) -> None:
        self.host = host
        saved = worker_auth.load_connection()
        self.state = ConnectionState(
            address=saved.base_url if saved else "",
            worker_id=saved.worker_id if saved else "",
            token=worker_auth.mask_token(worker_auth.load_token() or ""),
        )
        self.loop = heartbeat_loop.HeartbeatLoop(self._beat)
        self._heard = ""  # the last heartbeat answer written in the journal

    def props(self, msgs: Messages) -> ConnectionProps:
        return build_connection_props(msgs, self.state)

    @property
    def connected(self) -> bool:
        return self.state.status == STATE_OK

    def proxy_mode(self, address: str) -> api.ProxyMode:
        configured = cast("api.ProxyMode", self.host.config.network_proxy)
        return "direct" if worker_auth.is_loopback(address) else configured

    def _paired(self) -> tuple[str, str, str] | None:
        state, token = self.state, worker_auth.load_token()
        if not state.address or not state.worker_id or not token:
            return None
        return state.address, state.worker_id, token

    def api_target(self) -> delivery.ApiTarget | None:
        """Where delivery and claims go: the saved address, worker_id and token."""
        paired = self._paired()
        if paired is None:
            return None
        address, worker_id, token = paired
        base_url = address.rstrip("/") + heartbeat_call.API_SUFFIX
        return delivery.ApiTarget(base_url, worker_id, token, self.proxy_mode(address))

    def start_if_saved(self) -> None:
        """Panel start: a saved pairing connects by itself (heartbeat now, then every 30 s)."""
        if self._paired() is None:
            return
        self.host.connection_ok()
        self._checking(self.state.address, self.state.worker_id, self.state.token)
        self.loop.now()

    def pair(self, key_text: str) -> None:
        """Yhdistä: parse the pasted key, save it, connect with it; an empty field: nothing."""
        if not key_text.strip():
            self.state = replace(self.state, key_error=None)
            self.host.refresh()
            return
        try:
            key = worker_auth.parse_pairing_key(key_text)
        except worker_auth.PairingKeyError as exc:
            self.state = replace(self.state, key_error=exc)
            self.host.refresh()
            return
        worker_auth.save_pairing(key)
        self._checking(key.base_url, key.worker_id, worker_auth.mask_token(key.token))
        self.loop.now()

    def reconnect(self) -> None:
        """Yhdistä uudelleen: a heartbeat at once with the saved key."""
        if self._paired() is not None:
            self._checking(self.state.address, self.state.worker_id, self.state.token)
            self.loop.now()

    def watch(self) -> None:
        """Every second (main thread): the clock runs while paired; an attempt stuck past
        its time-out shows as Hidas yhteys with the seconds it has taken."""
        if self._paired() is None:
            return
        self.loop.ensure()
        running = self.loop.running_for()
        if running > heartbeat_loop.HEARTBEAT_TIMEOUT_S + STUCK_GRACE_S:
            self.state = replace(self.state, status=STATE_SLOW, slow_s=int(running))
            self.host.refresh()

    def _checking(self, address: str, worker_id: str, masked_token: str) -> None:
        self.state = ConnectionState(
            address=address, worker_id=worker_id, token=masked_token, status=STATE_CHECKING,
            testing=True, last_heartbeat=self._last_heartbeat(address, worker_id),
        )
        self.host.refresh()

    def _last_heartbeat(self, address: str, worker_id: str) -> datetime | None:
        """The last answered heartbeat stays shown while the same worker is tried again."""
        return self.state.last_heartbeat if self._is_current(address, worker_id) else None

    def _is_current(self, address: str, worker_id: str) -> bool:
        return (address, worker_id) == (self.state.address, self.state.worker_id)

    def _beat(self) -> None:
        """One heartbeat (the clock's thread); the outcome goes to the main thread."""
        paired = self._paired()
        if paired is None:
            return
        address, worker_id, token = paired
        started = time.monotonic()
        try:
            heartbeat_call.send(self.host, address, worker_id, token,
                                self.proxy_mode(address))
        except api.ApiError as exc:
            slow_s = timed_out(exc, time.monotonic() - started, heartbeat_loop.HEARTBEAT_TIMEOUT_S)
            self._journal(heartbeat_line(exc.status, exc.error, slow_s))
            if not slow_s:  # slow is not Ei verkkoa, in Lahetys neither
                self.host.heartbeat_failed(exc.status)
            self.host.post(functools.partial(self._apply_error, address, worker_id, exc, slow_s))
            return
        except Exception as exc:  # a fault inside the panel: shown, the clock goes on
            self._journal(f"heartbeat: {type(exc).__name__} in the panel: {str(exc)[:160]}")
            self.host.post(functools.partial(self._apply_panel, address, worker_id, exc))
            return
        self._journal(heartbeat_line(200, None))
        self.host.post(functools.partial(self._apply_ok, address, worker_id))

    def _journal(self, line: str) -> None:
        """A changed heartbeat answer goes in the journal (not one line every 30 s)."""
        if line != self._heard:
            self._heard = line
            runtime.journal("http", line)

    def _apply_ok(self, address: str, worker_id: str) -> None:
        if not self._is_current(address, worker_id):
            return  # an answer for a key that was replaced meanwhile
        self.state = ConnectionState(
            address=address, worker_id=worker_id, token=self.state.token,
            status=STATE_OK, last_heartbeat=datetime.now(UTC),
        )
        self.host.refresh()
        self.host.connection_ok()

    def _apply_error(self, address: str, worker_id: str, exc: api.ApiError, slow_s: int) -> None:
        if not self._is_current(address, worker_id):
            return
        status = STATE_SLOW if slow_s else STATE_REJECTED if exc.status == 401 else STATE_ERROR
        body = exc.error
        detail = (body.detail or body.code) if body else str(exc) if not exc.status else ""
        self.state = ConnectionState(
            address=address, worker_id=worker_id, token=self.state.token, status=status,
            error_detail=detail, error_status=exc.status, slow_s=slow_s,
            last_heartbeat=self.state.last_heartbeat,
        )
        self.host.refresh()

    def _apply_panel(self, address: str, worker_id: str, exc: Exception) -> None:
        if self._is_current(address, worker_id):
            self.state = replace(self.state, status=STATE_PANEL, testing=False,
                                 error_detail=f"{type(exc).__name__}: {str(exc)[:120]}")
            self.host.refresh()
