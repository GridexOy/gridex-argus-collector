"""Contract-shaped request payloads for the tests (all valid unless a test breaks them)."""

from __future__ import annotations

import uuid
from typing import Any

from contract_server.tests.client import WORKER_ID
from contract_server.util import Json, sha256_hex

HOST = "example.fi"
WHEN = "2026-10-04T12:00:00Z"
POLICY: Json = {
    "max_active_seconds": 1800,
    "max_pages": 200,
    "max_browser_actions": 400,
    "cloud_budget_eur": 0,
    "human_assistance": True,
    "auto_continue": False,
    "max_runs": 6,
    "max_campaign_active_seconds": 10800,
    "max_states": 300,
    "campaign_max_pages": 600,
    "campaign_max_states": 900,
    "campaign_max_browser_actions": 1200,
    "campaign_cloud_budget_eur": 0,
}
PAGE = (
    "<html><head><title>Contact</title><script>var phone = '000';</script>"
    "<style>p { color: red; }</style></head><body>"
    '<div class="card"><h3>Anna Virtanen</h3><p>Sales Manager</p>'
    "<p>+358 40 123 4567</p><p>anna.virtanen@example.fi</p></div>"
    "<footer>Switchboard +358 9 555 0100 &amp; info@example.fi</footer></body></html>"
)


def company(company_id: str = "c1", host: str = HOST, **overrides: Any) -> Json:
    body: Json = {
        "company_id": company_id,
        "project_id": "p1",
        "company_name": f"Company {company_id}",
        "seed_urls": [f"https://{host}/"],
        "scope": {
            "geography": "specified",
            "priority_countries": ["FI"],
            "priority_languages": ["fi"],
            "approved_hosts": [{"host": host, "basis": "seed", "evidence_id": None}],
            "include_contact_documents": False,
            "include_historical_observations": False,
        },
        "policy": dict(POLICY),
        "participation_status": "confirmed",
        "participation_claim_id": f"claim-{company_id}",
        "override_reason": None,
        "rerun_reason": None,
    }
    body.update(overrides)
    return body


def batch_body(*companies: Json, client_request_id: str | None = None) -> Json:
    return {
        "client_request_id": client_request_id or str(uuid.uuid4()),
        "companies": list(companies) or [company()],
    }


def capabilities() -> Json:
    return {
        "http": True,
        "browser": True,
        "vision": False,
        "model": True,
        "document_formats": [],
        "release_level": "M1",
    }


def heartbeat_body(
    active: list[Json] | None = None,
    acks: list[Json] | None = None,
    worker_id: str = WORKER_ID,
    outbox_pending: int = 0,
    schema_versions: tuple[str, ...] = ("1.1",),
) -> Json:
    return {
        "worker_id": worker_id,
        "worker_version": "0.4.2.0",
        "schema_versions": list(schema_versions),
        "capabilities": capabilities(),
        "collecting": True,
        "active_jobs": active or [],
        "outbox_pending": outbox_pending,
        "free_job_slots": 1,
        "browser_available": True,
        "model_available": True,
        "acknowledgements": acks or [],
    }


def claim_body(max_jobs: int = 8, worker_id: str = WORKER_ID) -> Json:
    return {"worker_id": worker_id, "max_jobs": max_jobs, "capabilities": capabilities()}


def active_lease(lease: Json) -> Json:
    keys = ("job_id", "run_id", "execution_token", "lease_generation")
    return {key: lease[key] for key in keys}


def metadata(
    lease: Json, company_id: str, data: bytes, evidence_id: str, /, **overrides: Any
) -> Json:
    body: Json = {
        "evidence_id": evidence_id,
        "job_id": lease["job_id"],
        "run_id": lease["run_id"],
        "company_id": company_id,
        "source_url": f"https://{HOST}/contact",
        "final_url": f"https://www.{HOST}/contact",
        "source_kind": "http_html",
        "mime_type": "text/html",
        "fetched_at": WHEN,
        "sha256": sha256_hex(data),
        "byte_length": len(data),
        "capture_truncated": False,
        "redacted": False,
        "extractor_version": "test-1",
    }
    body.update(overrides)
    return body


def event(lease: Json, seq: int, kind: str, payload: Json, event_id: str | None = None) -> Json:
    return {
        "event_id": event_id or str(uuid.uuid4()),
        "job_id": lease["job_id"],
        "run_id": lease["run_id"],
        "seq": seq,
        "occurred_at": WHEN,
        "type": kind,
        "schema_version": "1.1",
        "payload": payload,
    }


def events_body(token: str, events: list[Json]) -> Json:
    return {"schema_version": "1.1", "execution_token": token, "events": events}
