"""System-role calls the contract tests need (ARGUS creates batches, controls jobs).

Plain JSON over urllib: the worker never calls these, so the generated client
does not cover them; the payloads follow the OpenAPI schemas literally.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
import uuid
from typing import Any

DIRECT = urllib.request.build_opener(urllib.request.ProxyHandler({}))
POLICY = {
    "max_active_seconds": 1800, "max_pages": 200, "max_browser_actions": 400,
    "cloud_budget_eur": 0, "human_assistance": True, "auto_continue": False,
    "max_states": 300, "campaign_max_pages": 600, "campaign_max_states": 900,
    "campaign_max_browser_actions": 1200, "campaign_cloud_budget_eur": 0,
}


def company(host: str = "contract.example", **overrides: Any) -> dict[str, Any]:
    cid = "contract-" + uuid.uuid4().hex[:8]
    item: dict[str, Any] = {
        "company_id": cid, "project_id": "contract-tests", "company_name": f"Company {cid}",
        "seed_urls": [f"https://{host}/"],
        "scope": {"geography": "specified", "priority_countries": ["FI"],
                  "priority_languages": ["fi", "en"],
                  "approved_hosts": [{"host": host, "basis": "seed", "evidence_id": None}],
                  "include_contact_documents": False, "include_historical_observations": False},
        "policy": dict(POLICY), "participation_status": "confirmed",
        "participation_claim_id": f"claim-{cid}", "override_reason": None, "rerun_reason": None,
    }
    item.update(overrides)
    return item


class SystemClient:
    def __init__(self, base_url: str, token: str) -> None:
        self.base_url, self.token = base_url.rstrip("/"), token

    def call(self, method: str, path: str, body: object = None) -> tuple[int, Any]:
        data = None if body is None else json.dumps(body).encode("utf-8")
        headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
        req = urllib.request.Request(self.base_url + path, data=data, headers=headers,
                                     method=method)
        try:
            with DIRECT.open(req, timeout=15) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            return err.code, json.loads(err.read().decode("utf-8") or "{}")

    def batch(self, companies: list[dict[str, Any]]) -> tuple[int, Any]:
        body = {"client_request_id": str(uuid.uuid4()), "companies": companies}
        return self.call("POST", "/batches", body)

    def job(self, job_id: str) -> dict[str, Any]:
        status, data = self.call("GET", f"/jobs/{job_id}")
        assert status == 200, data
        return dict(data)

    def control(self, job_id: str, action: str) -> dict[str, Any]:
        body = {"client_request_id": str(uuid.uuid4()), "action": action,
                "expected_state_revision": self.job(job_id)["state_revision"]}
        status, data = self.call("POST", f"/jobs/{job_id}/control", body)
        assert status == 200, data
        return dict(data)
