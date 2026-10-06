"""Claimed-job samples and literal wire (JSON) examples for the api_client tests."""

from __future__ import annotations

from typing import Any

from argus_collector.api_client import contract as api
from argus_collector.api_client.tests import samples

ERROR = {"code": "sequence_gap", "detail": "seq 5 after 3", "retryable": False, "request_id": "r-1"}
EVIDENCE_RESPONSE = {"evidence_id": "e-1", "snapshot_id": None, "status": "accepted", "sha256": "f"}
POLICY: dict[str, Any] = {
    "max_active_seconds": 1800,
    "max_pages": 200,
    "max_browser_actions": 400,
    "cloud_budget_eur": 0.0,
    "human_assistance": False,
    "max_runs": 3,
    "max_states": 300,
    "campaign_max_pages": 600,
    "campaign_max_states": 900,
    "campaign_max_browser_actions": 1200,
    "campaign_cloud_budget_eur": 0.0,
}
SCOPE: dict[str, Any] = {
    "geography": "specified",
    "priority_countries": ["FI"],
    "priority_languages": ["fi"],
    "approved_hosts": [{"host": "example.fi", "basis": "seed", "evidence_id": None}],
    "include_contact_documents": True,
    "include_historical_observations": False,
    "restrictions": ["no_login"],
}
JOB: dict[str, Any] = {
    "schema_version": "1.1",
    "batch_id": "batch-1",
    "job_id": "job-1",
    "company_id": "company-1",
    "project_id": None,
    "company_name": "Example Oy",
    "seed_urls": ["https://example.fi/"],
    "scope": SCOPE,
    "policy": POLICY,
    "participation_status": "confirmed",
    "participation_claim_id": "claim-1",
    "override_reason": None,
    "rerun_reason": None,
}
LEASE = {
    "job_id": "job-1",
    "run_id": "run-1",
    "execution_token": "exec-1",
    "lease_generation": 1,
    "lease_expires_at": "2026-10-04T12:03:00Z",
}
KNOWN_CONTACT = {
    "canonical_contact_id": "cc-1",
    "entity_type": "person",
    "fields": {"email": "matti@example.fi", "phone": None},
    "last_seen_at": None,
    "channel_status": "published_direct",
}
CLAIMED_JOB = {
    "job": JOB,
    "lease": LEASE,
    "checkpoint": None,
    "routes": [],
    "known_contacts": [KNOWN_CONTACT],
}
CLAIM_RESPONSE = {"server_time": samples.AT, "jobs": [CLAIMED_JOB]}
EVENT_RESULT = {
    "event_id": "ev-1",
    "seq": 1,
    "status": "accepted",
    "code": None,
    "canonical_contact_id": None,
    "server_revision": 7,
    "state_applied": True,
    "channel_status": None,
}
EVENT_RESULT_CONTACT = {
    **EVENT_RESULT,
    "event_id": "ev-3",
    "seq": 3,
    "canonical_contact_id": "cc-1",
    "channel_status": "published_direct",
}
EVENTS_RESPONSE = {
    "results": [EVENT_RESULT, EVENT_RESULT_CONTACT],
    "last_contiguous_seq": 3,
    "job_state": "running",
    "next_run_scheduled": False,
}
RECONCILE_RESPONSE = {
    "mode": "drain_only",
    "lease": {**LEASE, "execution_token": "drain-1", "lease_generation": 2},
    "accepted_event_ids": ["ev-1"],
    "accepted_evidence_ids": [],
    "missing_evidence_ids": ["evd-2"],
    "last_contiguous_seq": 1,
    "job_state": "cancelled",
}


def job_definition() -> api.JobDefinition:
    policy = api.Policy(
        max_active_seconds=900,
        max_pages=50,
        max_browser_actions=100,
        cloud_budget_eur=0.0,
        human_assistance=True,
        max_states=100,
        campaign_max_pages=150,
        campaign_max_states=300,
        campaign_max_browser_actions=300,
        campaign_cloud_budget_eur=0.0,
        auto_continue=False,
    )
    override = api.ParticipationStatus.OWNER_OVERRIDE
    return api.JobDefinition(
        api.JobDefinitionSchemaVersion("1.1"), "batch-1", "job-1", "company-1", "project-1",
        "Example Oy", ["https://example.fi/"],
        samples.scope(), policy, override, None, "owner says so", None,
    )  # fmt: skip


def claimed_job(checkpoint: api.Checkpoint | None) -> api.ClaimedJob:
    lease = api.Lease("job-1", "run-2", "exec-2", 3, "2026-10-04T12:03:00Z")
    contact = api.KnownContact(
        "cc-1", api.KnownContactEntityType.PERSON, {"email": "matti@example.fi"}, samples.AT,
        api.ChannelStatus.STALE,
    )  # fmt: skip
    return api.ClaimedJob(job_definition(), lease, checkpoint, [samples.route()], [contact])
