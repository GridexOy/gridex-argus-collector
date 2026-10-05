"""Yhteys controller: pairing key, Yhdistä and the 30 s heartbeat loop (TZ_TANDEM A1).

Yhdistä parses the pasted `argus://pair?...` key, saves it (address and
worker_id plain, token with DPAPI) and sends a heartbeat at once. A saved
key connects by itself at every panel start; the loop then re-sends a
heartbeat every 30 s and keeps trying while ARGUS cannot be reached. A
rejected token stops the loop until a new key is pasted.
"""

from __future__ import annotations

import functools
import threading
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from typing import Protocol, cast

from argus_collector.api_client import contract as api
from argus_collector.delivery import contract as delivery
from argus_collector.diagnostics import contract as diagnostics
from argus_collector.runtime import contract as runtime
from argus_collector.scheduler import contract as scheduler
from argus_collector.ui.app_collect import capabilities_of
from argus_collector.ui.connection_lines import (
    STATE_CHECKING,
    STATE_ERROR,
    STATE_OK,
    STATE_REJECTED,
    ConnectionProps,
    ConnectionState,
)
from argus_collector.ui.connection_lines import connection_props as build_connection_props
from argus_collector.ui.repository import Messages
from argus_collector.worker_auth import contract as worker_auth

HEARTBEAT_INTERVAL_S = 30.0
SCHEMA_VERSIONS = ["1.1"]
API_SUFFIX = "/api/collector"


class Host(Protocol):
    config: runtime.Config
    report: diagnostics.Report | None

    def post(self, action: Callable[[], None]) -> None: ...
    def refresh(self) -> None: ...
    def heartbeat_fields(self) -> scheduler.HeartbeatFields: ...
    def heartbeat_answered(self, response: api.HeartbeatResponse, acks: list[str]) -> None: ...
    def heartbeat_failed(self, status: int) -> None: ...
    def connection_ok(self) -> None: ...


class ConnectionController:
    def __init__(self, host: Host) -> None:
        self.host = host
        saved = worker_auth.load_connection()
        self.state = ConnectionState(
            address=saved.base_url if saved else "",
            worker_id=saved.worker_id if saved else "",
            token=worker_auth.mask_token(worker_auth.load_token() or ""),
        )
        self._stop = threading.Event()
        self._loop_thread: threading.Thread | None = None

    def props(self, msgs: Messages) -> ConnectionProps:
        return build_connection_props(msgs, self.state)

    @property
    def connected(self) -> bool:
        return self.state.status == STATE_OK

    def proxy_mode(self, address: str) -> api.ProxyMode:
        configured = cast("api.ProxyMode", self.host.config.network_proxy)
        return "direct" if worker_auth.is_loopback(address) else configured

    def api_target(self) -> delivery.ApiTarget | None:
        """Where delivery and claims go: the saved address, worker_id and token."""
        state, token = self.state, worker_auth.load_token()
        if not state.address or not state.worker_id or not token:
            return None
        base_url = state.address.rstrip("/") + API_SUFFIX
        return delivery.ApiTarget(base_url, state.worker_id, token, self.proxy_mode(state.address))

    def start_if_saved(self) -> None:
        """Panel start: a saved pairing connects by itself (heartbeat now, then every 30 s)."""
        token = worker_auth.load_token()
        if not self.state.address or not self.state.worker_id or not token:
            return
        self.host.connection_ok()
        self._connect(self.state.address, self.state.worker_id, token)

    def pair(self, key_text: str) -> None:
        """Yhdistä: parse the pasted key, save it, connect with it."""
        try:
            key = worker_auth.parse_pairing_key(key_text)
        except worker_auth.PairingKeyError as exc:
            self.state = replace(self.state, key_error=exc)
            self.host.refresh()
            return
        worker_auth.save_pairing(key)
        self._connect(key.base_url, key.worker_id, key.token)

    def _connect(self, address: str, worker_id: str, token: str) -> None:
        self.state = ConnectionState(
            address=address, worker_id=worker_id, token=worker_auth.mask_token(token),
            status=STATE_CHECKING, testing=True,
            last_heartbeat=self._last_heartbeat(address, worker_id),
        )
        self.host.refresh()
        threading.Thread(
            target=self._attempt, args=(address, worker_id, token), name="heartbeat-connect"
        ).start()
        self._start_loop()

    def _last_heartbeat(self, address: str, worker_id: str) -> datetime | None:
        """The last answered heartbeat stays shown while the same worker is tried again."""
        return self.state.last_heartbeat if self._is_current(address, worker_id) else None

    def _is_current(self, address: str, worker_id: str) -> bool:
        return (address, worker_id) == (self.state.address, self.state.worker_id)

    def _attempt(self, address: str, worker_id: str, token: str) -> None:
        try:
            self._call(address, worker_id, token)
        except api.ApiError as exc:
            self.host.heartbeat_failed(exc.status)
            self.host.post(functools.partial(self._apply_error, address, worker_id, exc))
            return
        self.host.post(functools.partial(self._apply_ok, address, worker_id))

    def _call(self, address: str, worker_id: str, token: str) -> api.HeartbeatResponse:
        """One heartbeat with the collector's leases, outbox, slots and command acks;
        the answer (renewals, commands) goes back to the collector."""
        caps = capabilities_of(self.host.report)
        fields = self.host.heartbeat_fields()
        request = api.HeartbeatRequest(
            worker_id=worker_id,
            worker_version=runtime.current_version_status().file_version,
            schema_versions=SCHEMA_VERSIONS,
            capabilities=caps,
            collecting=fields.collecting,
            active_jobs=fields.active_jobs,
            outbox_pending=fields.outbox_pending,
            free_job_slots=fields.free_job_slots,
            browser_available=caps.browser,
            model_available=caps.model,
            acknowledgements=fields.acknowledgements,
        )
        base_url = address.rstrip("/") + API_SUFFIX
        response = api.heartbeat(base_url, token, request, proxy_mode=self.proxy_mode(address))
        self.host.heartbeat_answered(response, [a.command_id for a in fields.acknowledgements])
        return response

    def _apply_ok(self, address: str, worker_id: str) -> None:
        if not self._is_current(address, worker_id):
            return  # an answer for a key that was replaced meanwhile
        self.state = ConnectionState(
            address=address, worker_id=worker_id, token=self.state.token,
            status=STATE_OK, last_heartbeat=datetime.now(UTC),
        )
        self.host.refresh()
        self.host.connection_ok()

    def _apply_error(self, address: str, worker_id: str, exc: api.ApiError) -> None:
        if not self._is_current(address, worker_id):
            return
        status = STATE_REJECTED if exc.status == 401 else STATE_ERROR
        detail = exc.error.detail if exc.error is not None else str(exc)
        self.state = ConnectionState(
            address=address, worker_id=worker_id, token=self.state.token,
            status=status, error_detail=detail, last_heartbeat=self.state.last_heartbeat,
        )
        self.host.refresh()

    def _start_loop(self) -> None:
        if self._loop_thread is not None and self._loop_thread.is_alive():
            return
        self._stop.clear()
        self._loop_thread = threading.Thread(target=self._loop, name="heartbeat-loop", daemon=True)
        self._loop_thread.start()

    def _loop(self) -> None:
        while not self._stop.wait(HEARTBEAT_INTERVAL_S):
            state = self.state
            token = worker_auth.load_token()
            if not state.worker_id or not token or state.status == STATE_REJECTED:
                continue
            self._attempt(state.address, state.worker_id, token)
