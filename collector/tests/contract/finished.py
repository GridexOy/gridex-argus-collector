"""A minimal job.finished built with the generated types (contract tests only)."""

from __future__ import annotations

import uuid

from argus_collector.api_client import contract as api

from collector.tests.contract.worker import now


def counts() -> api.Counts:
    return api.Counts(persons=0, organization_channels=0, other_entities=0, observations=0,
                      pages_processed=1, browser_actions=0, evidence_count=0, gaps=0,
                      outbox_pending=0, states_processed=1)


def finished(job: api.ClaimedJob, seq: int, last_content_seq: int) -> api.JobFinishedEvent:
    coverage = api.Coverage(
        frontier_status=api.CoverageFrontierStatus("exhausted"),
        confirmation=api.CoverageConfirmation("unverified"),
        basis=api.CoverageBasis("frontier_exhausted"), scope_description="1 page",
        expected_count=None, found_count=0, gap_count=0, evidence_ids=[],
    )
    checkpoint = api.Checkpoint(frontier_items=[], checkpoint_evidence_id=None, route_refs=[],
                                active_seconds_consumed=1.0, pages_consumed=1,
                                actions_consumed=0)
    budget = api.BudgetState(campaign_active_seconds=1.0, campaign_pages=1, campaign_states=1,
                             campaign_browser_actions=0, campaign_cloud_eur=0.0, runs_used=1)
    summary = api.FinishedPayloadFreshnessSummary(reconfirmed=0, changed=0,
                                                  not_seen_in_checked_scope=0, not_checked=0)
    payload = api.FinishedPayload(
        run_result_status=api.FinishedPayloadRunResultStatus("completed"),
        completion_reason=api.FinishedPayloadCompletionReason("no_contacts_in_checked_scope"),
        scope=job.job.scope, counts=counts(), coverage=coverage, checkpoint=checkpoint, gaps=[],
        last_content_seq=last_content_seq, active_seconds=1.0, wall_seconds=2.0, models=[],
        freshness_summary=summary, continuation_requested=False, budget=budget,
    )
    return api.JobFinishedEvent(event_id=str(uuid.uuid4()), job_id=job.job.job_id,
                                run_id=job.lease.run_id, seq=seq, occurred_at=now(),
                                payload=payload)
