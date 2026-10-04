"""Yhteys controller: Testaa yhteys and the 30s heartbeat loop (TZ_TANDEM A1)."""

from __future__ import annotations

import functools
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol, cast

from argus_collector.api_client import contract as api
from argus_collector.diagnostics import contract as diagnostics
from argus_collector.runtime import contract as runtime
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


class WalkHost(Protocol):
    @property
    def walking(self) -> bool: ...


class Host(Protocol):
    config: runtime.Config
    report: diagnostics.Report | None

    @property
    def walk(self) -> WalkHost: ...

    def post(self, action: Callable[[], None]) -> None: ...
    def refresh(self) -> None: ...


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

    def start_if_saved(self) -> None:
        if self.state.worker_id and worker_auth.load_token():
            self._start_loop()

    def test_connection(self, address: str, worker_id: str, token_input: str) -> None:
        token = token_input.strip() or worker_auth.load_token() or ""
        address, worker_id = address.strip(), worker_id.strip()
        self.state = ConnectionState(
            address=address, worker_id=worker_id, token=self.state.token, testing=True
        )
        self.host.refresh()
        threading.Thread(
            target=self._attempt, args=(address, worker_id, token, True), name="heartbeat-test"
        ).start()

    def _attempt(self, address: str, worker_id: str, token: str, persist_on_success: bool) -> None:
        try:
            self._call(address, worker_id, token)
        except api.ApiError as exc:
            self.host.post(functools.partial(self._apply_error, address, worker_id, exc))
            return
        self.host.post(
            functools.partial(self._apply_ok, address, worker_id, token, persist_on_success)
        )

    def _call(self, address: str, worker_id: str, token: str) -> api.HeartbeatResponse:
        report = self.host.report
        chrome_ok = report is not None and report.states.chrome is diagnostics.ChromeState.AVAILABLE
        model_ok = report is not None and report.states.model is not diagnostics.ModelState.NONE
        request = api.HeartbeatRequest(
            worker_id=worker_id,
            worker_version=runtime.current_version_status().file_version,
            schema_versions=SCHEMA_VERSIONS,
            capabilities=api.Capabilities(
                http=True,
                browser=chrome_ok,
                vision=False,
                model=model_ok,
                document_formats=[],
                release_level=api.CapabilitiesReleaseLevel.M1,
            ),
            collecting=self.host.walk.walking,
            active_jobs=[],
            outbox_pending=0,
            free_job_slots=0 if self.host.walk.walking else 1,
            browser_available=chrome_ok,
            model_available=model_ok,
            acknowledgements=[],
        )
        configured = cast("api.ProxyMode", self.host.config.network_proxy)
        proxy_mode: api.ProxyMode = "direct" if _is_loopback(address) else configured
        base_url = address.rstrip("/") + API_SUFFIX
        return api.heartbeat(base_url, token, request, proxy_mode=proxy_mode)

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
        self._start_loop()

    def _apply_error(self, address: str, worker_id: str, exc: api.ApiError) -> None:
        status = "rejected" if exc.status == 401 else "error"
        detail = exc.error.detail if exc.error is not None else str(exc)
        self.state = ConnectionState(
            address=address, worker_id=worker_id, token=self.state.token,
            status=status, error_detail=detail,
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
