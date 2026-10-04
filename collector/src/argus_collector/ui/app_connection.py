"""Yhteys controller: Testaa yhteys and the 30s heartbeat loop (TZ_TANDEM A1)."""

from __future__ import annotations

import functools
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol, cast

from argus_collector.api_client import contract as api
from argus_collector.delivery import contract as delivery
from argus_collector.diagnostics import contract as diagnostics
from argus_collector.runtime import contract as runtime
from argus_collector.scheduler import contract as scheduler
from argus_collector.ui.app_collect import capabilities_of
from argus_collector.ui.connection_lines import ConnectionProps, ConnectionState
from argus_collector.ui.connection_lines import connection_props as build_connection_props
from argus_collector.ui.repository import Messages
from argus_collector.worker_auth import contract as worker_auth

HEARTBEAT_INTERVAL_S = 30.0
SCHEMA_VERSIONS = ["1.1"]
API_SUFFIX = "/api/collector"
LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "::1")


def _is_loopback(address: str) -> bool:
    host = address.split("://", 1)[-1].split("/", 1)[0].split(":", 1)[0]
    return host in LOOPBACK_HOSTS


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
            address=saved.base_url if saved else host.config.argus_base_url,
            worker_id=saved.worker_id if saved else "",
            token=worker_auth.mask_token(worker_auth.load_token() or ""),
        )
        self._stop = threading.Event()
        self._loop_thread: threading.Thread | None = None

    def props(self, msgs: Messages) -> ConnectionProps:
        return build_connection_props(msgs, self.state)

    @property
    def connected(self) -> bool:
        return self.state.status == "ok"

    def proxy_mode(self, address: str) -> api.ProxyMode:
        configured = cast("api.ProxyMode", self.host.config.network_proxy)
        return "direct" if _is_loopback(address) else configured

    def api_target(self) -> delivery.ApiTarget | None:
        """Where delivery and claims go: the saved address, worker_id and token."""
        state, token = self.state, worker_auth.load_token()
        if not state.address or not state.worker_id or not token:
            return None
        base_url = state.address.rstrip("/") + API_SUFFIX
        return delivery.ApiTarget(base_url, state.worker_id, token, self.proxy_mode(state.address))

    def start_if_saved(self) -> None:
        if self.state.worker_id and worker_auth.load_token():
            self.host.connection_ok()
            self._start_loop()

    def test_connection(self, address: str, worker_id: str, token_input: str) -> None:
        token = token_input.strip() or worker_auth.load_token() or ""
        address, worker_id = address.strip(), worker_id.strip()
        self.state = ConnectionState(
            address=address, worker_id=worker_id, token=self.state.token, testing=True,
            last_heartbeat=self._last_heartbeat(address, worker_id),
        )
        self.host.refresh()
        threading.Thread(
            target=self._attempt, args=(address, worker_id, token, True), name="heartbeat-test"
        ).start()

    def _last_heartbeat(self, address: str, worker_id: str) -> datetime | None:
        """The last answered heartbeat stays shown while the same worker is tried again."""
        same = (address, worker_id) == (self.state.address, self.state.worker_id)
        return self.state.last_heartbeat if same else None

    def _attempt(self, address: str, worker_id: str, token: str, persist_on_success: bool) -> None:
        try:
            self._call(address, worker_id, token)
        except api.ApiError as exc:
            self.host.heartbeat_failed(exc.status)
            self.host.post(functools.partial(self._apply_error, address, worker_id, exc))
            return
        self.host.post(
            functools.partial(self._apply_ok, address, worker_id, token, persist_on_success)
        )

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

    def _apply_ok(self, address: str, worker_id: str, token: str, persist: bool) -> None:
        if persist:
            worker_auth.save_connection(address, worker_id)
            worker_auth.save_token(token)
        self.state = ConnectionState(
            address=address,
            worker_id=worker_id,
            token=worker_auth.mask_token(token),
            status="ok",
            last_heartbeat=datetime.now(UTC),
        )
        self.host.refresh()
        self.host.connection_ok()
        self._start_loop()

    def _apply_error(self, address: str, worker_id: str, exc: api.ApiError) -> None:
        status = "rejected" if exc.status == 401 else "error"
        detail = exc.error.detail if exc.error is not None else str(exc)
        self.state = ConnectionState(
            address=address, worker_id=worker_id, token=self.state.token,
            status=status, error_detail=detail,
            last_heartbeat=self._last_heartbeat(address, worker_id),
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
            if not state.worker_id or not token:
                continue
            self._attempt(state.address, state.worker_id, token, False)
