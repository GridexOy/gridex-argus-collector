"""Test stands for the collector: contract_server, fixture site, fake model.

`System` plays ARGUS's System role over HTTP (batches, control, job status,
the stand-only `/_stand` views); `make_collector` builds a headless
`Collector` on a temporary database, pointed at the contract server.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

from argus_collector.api_client import contract as api
from argus_collector.delivery import contract as delivery
from argus_collector.models.contract import ModelConfig
from argus_collector.scheduler import contract as scheduler
from contract_server import server as contract_server
from contract_server import stand
from test_site import companies, server

TOKEN, WORKER_ID, SYSTEM_TOKEN = "test-token-abc", "worker-main-pc", "system-token-xyz"
DIRECT = urllib.request.build_opener(urllib.request.ProxyHandler({}))
GOLD_DIR = Path(__file__).resolve().parents[5] / "test_site" / "gold"


def gold(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((GOLD_DIR / f"{name}.json").read_text(encoding="utf-8"))
    return data


def gold_persons() -> list[dict[str, Any]]:
    return [p for name in ("fixture_oy", "nordtec", "vogel") for p in gold(name)["persons"]]


class System:
    """ARGUS System calls against the contract server (stand-only views included)."""

    def __init__(self, srv: contract_server.ContractServer) -> None:
        self.base = contract_server.base_url(srv)

    def call(self, method: str, path: str, body: object = None) -> tuple[int, Any]:
        data = None if body is None else json.dumps(body).encode("utf-8")
        headers = {"Authorization": f"Bearer {SYSTEM_TOKEN}", "Content-Type": "application/json"}
        req = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with DIRECT.open(req, timeout=10) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            return err.code, json.loads(err.read().decode("utf-8"))

    def batch(self, site: ThreadingHTTPServer, ids: list[str], rerun: str | None = None,
              **policy: Any) -> dict[str, str]:
        """Batch of fixture companies -> {company_id: job_id} (`rerun`: rerun_reason)."""
        chosen = [c for c in companies.companies(site.server_address[1]) if c["company_id"] in ids]
        inputs = [stand.company_input(c, rerun) for c in chosen]
        for item in inputs:
            item["policy"].update(policy)
        body = {"client_request_id": str(uuid.uuid4()), "companies": inputs}
        status, data = self.call("POST", "/api/collector/batches", body)
        assert status == 201, data
        return {j["company_id"]: j["job_id"] for j in data["jobs"]}

    def job(self, job_id: str) -> dict[str, Any]:
        status, data = self.call("GET", f"/api/collector/jobs/{job_id}")
        assert status == 200, data
        return dict(data)

    def company(self, company_id: str) -> dict[str, Any]:
        status, data = self.call("GET", f"/_stand/companies/{company_id}/contacts")
        assert status == 200, data
        return dict(data)

    def contacts(self, job_id: str) -> dict[str, Any]:
        status, data = self.call("GET", f"/_stand/jobs/{job_id}/contacts")
        assert status == 200, data
        return dict(data)

    def control(self, job_id: str, action: str) -> dict[str, Any]:
        revision = self.job(job_id)["state_revision"]
        body = {"client_request_id": str(uuid.uuid4()), "action": action,
                "expected_state_revision": revision}
        status, data = self.call("POST", f"/api/collector/jobs/{job_id}/control", body)
        assert status == 200, data
        return dict(data)


def target_of(srv: contract_server.ContractServer) -> delivery.ApiTarget:
    return delivery.ApiTarget(
        contract_server.base_url(srv) + "/api/collector", WORKER_ID, TOKEN, "direct"
    )


def make_collector(
    tmp: Path,
    srv: contract_server.ContractServer,
    model_endpoint: str,
    stop_files: Callable[[], list[Path]] = lambda: [],
) -> scheduler.Collector:
    env = scheduler.WalkEnv(
        model=ModelConfig(model_endpoint, "fake-instruct"), headless=True,
        profile_dir=tmp / "profile", evidence_dir=tmp / "evidence", db_path=tmp / "collector.db",
        stop_files=(), version="0.4.3.0",
    )
    settings = scheduler.Settings(env=env, stop_files=stop_files, claim_interval_s=0.2,
                                  idle_wait_s=0.1)
    caps = api.Capabilities(http=True, browser=True, vision=False, model=True,
                            document_formats=[], release_level=api.CapabilitiesReleaseLevel("M1"))
    target = target_of(srv)
    return scheduler.Collector(settings, lambda: target, lambda: caps, lambda: None,
                               lambda _e: None)


def wait_for(predicate: Callable[[], bool], timeout_s: float = 240.0, step_s: float = 0.2) -> None:
    deadline = time.monotonic() + timeout_s
    while not predicate():
        if time.monotonic() > deadline:
            raise AssertionError("condition not reached in time")
        time.sleep(step_s)


def heartbeat(collector: scheduler.Collector, srv: contract_server.ContractServer) -> None:
    """One heartbeat as the panel sends it, answer applied to the collector."""
    fields = collector.heartbeat_fields()
    caps = api.Capabilities(http=True, browser=True, vision=False, model=True,
                            document_formats=[], release_level=api.CapabilitiesReleaseLevel("M1"))
    request = api.HeartbeatRequest(
        worker_id=WORKER_ID, worker_version="0.4.3.0", schema_versions=["1.1"],
        capabilities=caps, collecting=fields.collecting, active_jobs=fields.active_jobs,
        outbox_pending=fields.outbox_pending, free_job_slots=fields.free_job_slots,
        browser_available=True, model_available=True, acknowledgements=fields.acknowledgements,
    )
    response = api.heartbeat(target_of(srv).base_url, TOKEN, request, proxy_mode="direct")
    collector.apply_heartbeat(response, [a.command_id for a in fields.acknowledgements])


__all__ = ["server", "System", "gold", "gold_persons", "make_collector", "wait_for"]
