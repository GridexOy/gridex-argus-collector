"""Event payloads for the tests (valid against the contract by default)."""

from __future__ import annotations

import uuid
from typing import Any

from contract_server import openapi
from contract_server.tests.builders import HOST, WHEN
from contract_server.util import Json

ZERO_COUNTS: tuple[str, ...] = tuple(openapi.SCHEMAS["Counts"]["required"])


def observation(
    field: str,
    value: str,
    evidence_id: str,
    quote: str | None = None,
    binding: str = "card",
    status: str = "confirmed",
    locator: Json | None = None,
    observation_id: str | None = None,
) -> Json:
    return {
        "observation_id": observation_id or str(uuid.uuid4()),
        "field": field,
        "raw_value": value,
        "normalized_value": value,
        "extraction_status": status,
        "evidence_id": evidence_id,
        "locator": locator or {"kind": "dom", "value": "div.card", "text_sha256": "0" * 64},
        "quote": value if quote is None else quote,
        "change_kind": "new",
        "binding": binding,
    }


def field_audit(evidence_id: str) -> Json:
    item: Json = {
        "source_field": "phone",
        "disposition": "mapped",
        "observation_ids": [],
        "raw_value": None,
        "reason": "",
    }
    return {"evidence_id": evidence_id, "items": [item], "dropped_contact_fields": 0}


def contact(
    evidence_id: str,
    observations: list[Json],
    entity_type: str = "person",
    entity_id: str = "e1",
    relationship: str = "employee",
) -> Json:
    return {
        "entity_id": entity_id,
        "entity_type": entity_type,
        "relationship": relationship,
        "observations": observations,
        "field_audit": field_audit(evidence_id),
    }


def started() -> Json:
    return {"stage": "http", "worker_version": "0.4.2.0"}


def counts(**values: int) -> Json:
    body: Json = dict.fromkeys(ZERO_COUNTS, 0)
    body.update(values)
    return body


def coverage(**overrides: Any) -> Json:
    body: Json = {
        "frontier_status": "exhausted",
        "confirmation": "unverified",
        "basis": "frontier_exhausted",
        "scope_description": "contact pages",
        "expected_count": None,
        "found_count": 1,
        "gap_count": 0,
        "evidence_ids": [],
    }
    body.update(overrides)
    return body


def progress(**count_values: int) -> Json:
    return {
        "stage": "browser",
        "counts": counts(**count_values),
        "coverage": coverage(frontier_status="partial"),
        "active_seconds": 12.5,
        "transport_state": "online",
    }


def checkpoint(pages: int = 0) -> Json:
    return {
        "frontier_items": [],
        "checkpoint_evidence_id": None,
        "route_refs": [],
        "active_seconds_consumed": 10.0,
        "pages_consumed": pages,
        "actions_consumed": 0,
    }


def budget(pages: int = 3, runs: int = 1) -> Json:
    return {
        "campaign_active_seconds": 60.0,
        "campaign_pages": pages,
        "campaign_states": pages,
        "campaign_browser_actions": 0,
        "campaign_cloud_eur": 0,
        "runs_used": runs,
    }


def gap(resumable: bool = True) -> Json:
    return {
        "gap_id": str(uuid.uuid4()),
        "source_url": f"https://{HOST}/people?page=2",
        "state_key": "people:2",
        "reason": "budget_reached",
        "detail": "run page budget",
        "attempts": 1,
        "resumable": resumable,
    }


def finished(last_content_seq: int, status: str = "completed", **overrides: Any) -> Json:
    body: Json = {
        "run_result_status": status,
        "completion_reason": "frontier_exhausted" if status == "completed" else "budget_reached",
        "scope": {
            "geography": "specified",
            "priority_countries": ["FI"],
            "priority_languages": ["fi"],
            "approved_hosts": [{"host": HOST, "basis": "seed", "evidence_id": None}],
            "include_contact_documents": False,
            "include_historical_observations": False,
        },
        "counts": counts(persons=1, pages_processed=1, browser_actions=4, states_processed=2),
        "coverage": coverage(),
        "checkpoint": checkpoint(pages=3),
        "gaps": [],
        "last_content_seq": last_content_seq,
        "active_seconds": 60.0,
        "wall_seconds": 90.0,
        "models": [],
        "freshness_summary": dict.fromkeys(
            ("reconfirmed", "changed", "not_seen_in_checked_scope", "not_checked"), 0
        ),
        "continuation_requested": False,
        "budget": budget(),
    }
    body.update(overrides)
    return body


def source(evidence_ids: list[str] | None = None) -> Json:
    return {
        "source_id": str(uuid.uuid4()),
        "url": f"https://{HOST}/contact",
        "state_key": "contact",
        "parent_source_id": None,
        "status": "fetched_http",
        "evidence_ids": evidence_ids or [],
        "detail": "",
    }


def model_called() -> Json:
    usage = {
        "model_id": "qwen-test",
        "provider": "local",
        "quantization": None,
        "context_tokens": 4096,
        "input_tokens": 900,
        "output_tokens": 120,
        "cost_eur": 0,
        "purpose": "card_parsing",
        "started_at": WHEN,
        "duration_ms": 850,
        "local": True,
    }
    return {"usage": usage, "source_ids": []}
