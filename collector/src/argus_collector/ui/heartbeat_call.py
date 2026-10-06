"""One heartbeat request of Yhteys: the collector's leases, outbox, slots and command acks
go to ARGUS; the answer (renewals, commands) goes back to the collector."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from argus_collector.api_client import contract as api
from argus_collector.diagnostics import contract as diagnostics
from argus_collector.runtime import contract as runtime
from argus_collector.scheduler import contract as scheduler
from argus_collector.ui import heartbeat_loop
from argus_collector.ui.app_collect import capabilities_of

SCHEMA_VERSIONS = ["1.1", "1.2"]  # 1.2: refusals carry their rule (CONTRACT_3.1)
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


def send(host: Host, address: str, worker_id: str, token: str,
         proxy_mode: api.ProxyMode) -> api.HeartbeatResponse:
    """One heartbeat with the collector's leases, outbox, slots and command acks;
    the answer (renewals, commands) goes back to the collector."""
    caps = capabilities_of(host.report)
    fields = host.heartbeat_fields()
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
    response = api.heartbeat(base_url, token, request, proxy_mode=proxy_mode,
                             timeout_s=heartbeat_loop.HEARTBEAT_TIMEOUT_S)
    host.heartbeat_answered(response, [a.command_id for a in fields.acknowledgements])
    return response
