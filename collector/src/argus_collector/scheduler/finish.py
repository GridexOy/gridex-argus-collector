"""job.progress and job.finished payloads: counts, coverage, gaps, checkpoint, budget.

Crawl completion and coverage confirmation are separate (TZ_SELAIN 8.10):
without a catalog total the confirmation is always `unverified`, and
`completed` + `unverified` is the normal result; a directory that states
its size gives `expected_count` and, when all were found, `verified_*`.
"""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from typing import Any

from argus_collector.api_client import contract as api
from argus_collector.delivery import contract as delivery
from argus_collector.scheduler import repository as repo
from argus_collector.scheduler import service
from argus_collector.walk import contract as walk


@dataclass(frozen=True)
class RunFacts:
    """What job.finished reports about one run (and its campaign)."""

    job_id: str
    run_id: str
    hosts: tuple[str, ...]
    end_reason: str
    checkpoint: walk.WalkCheckpoint
    consumed: service.Consumed
    wall_seconds: float


def _uid(job_id: str, kind: str, key: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"argus-collector:{job_id}:{kind}:{key}"))


def counts(conn: sqlite3.Connection, facts: RunFacts) -> api.Counts:
    row = repo.job(conn, facts.job_id)
    by_type = repo.entity_counts(conn, facts.job_id)
    others = sum(n for kind, n in by_type.items() if kind not in ("person", "organization_channel"))
    cp = facts.checkpoint
    return api.Counts(
        persons=by_type.get("person", 0),
        organization_channels=by_type.get("organization_channel", 0),
        other_entities=others, observations=int(row["observations"]) if row else 0,
        pages_processed=cp.pages, browser_actions=cp.actions,
        evidence_count=int(row["sources"]) if row else 0, gaps=len(cp.gaps),
        outbox_pending=delivery.job_totals(conn, facts.job_id)[0],
        states_processed=len(cp.seen_keys),
    )


def _scope(facts: RunFacts) -> str:
    cp = facts.checkpoint
    parts = [f"{cp.pages} pages and {len(cp.seen_keys)} page states on {', '.join(facts.hosts)}"]
    if cp.acted:
        parts.append(f"{len(cp.acted)} tabs, sections or country choices opened")
    if cp.declared_total:
        parts.append(f"the directory states {cp.declared_total} records")
    parts.append(f"{len(cp.frontier)} links left unvisited, {len(cp.gaps)} gaps")
    return "; ".join(parts)


def coverage(facts: RunFacts, found: int) -> api.Coverage:
    """basis: catalog_total when a directory stated its size, frontier_exhausted when the
    relevant frontier was walked to its end, else unknown (TZ_SELAIN 8.10)."""
    cp = facts.checkpoint
    status = service.frontier_status(facts.end_reason, cp.pages)
    basis = "frontier_exhausted" if status == "exhausted" else "unknown"
    confirmation = "unverified"
    if cp.declared_total:
        basis = "catalog_total"
        if found >= cp.declared_total:
            confirmation = "verified_against_catalog_total"
    return api.Coverage(
        frontier_status=api.CoverageFrontierStatus(status),
        confirmation=api.CoverageConfirmation(confirmation), basis=api.CoverageBasis(basis),
        scope_description=_scope(facts), expected_count=cp.declared_total or None,
        found_count=found, gap_count=len(cp.gaps), evidence_ids=[],
    )


def gaps(facts: RunFacts) -> list[api.Gap]:
    return [
        api.Gap(
            gap_id=_uid(facts.job_id, "gap", f"{g.state_key}|{g.reason}"), source_url=g.url,
            state_key=g.state_key, reason=api.GapReason(g.reason), detail=g.detail,
            attempts=1, resumable=g.resumable,
        )
        for g in facts.checkpoint.gaps
    ]


def server_checkpoint(facts: RunFacts) -> api.Checkpoint:
    cp, used = facts.checkpoint, facts.consumed
    items = [
        api.FrontierItem(
            source_id=_uid(facts.job_id, "frontier", key), url=link.url, state_key=key,
            parent_source_id=None, priority=max(0, link.score),
            method=api.FrontierItemMethod("browser"), state="queued_browser", filters={},
            cursor=None, attempts=0, route_id=None,
        )
        for key, link in cp.frontier.items()
    ]
    return api.Checkpoint(
        frontier_items=items, checkpoint_evidence_id=None, route_refs=[],
        active_seconds_consumed=used.seconds + cp.active_seconds,
        pages_consumed=used.pages + cp.pages, actions_consumed=used.actions + cp.actions,
    )


def models_used(conn: sqlite3.Connection, run_id: str) -> list[api.ModelUsage]:
    """model.called usages of the run summed per (model, purpose)."""
    totals: dict[tuple[str, str], dict[str, Any]] = {}
    for payload in delivery.run_events(conn, run_id, "model.called"):
        raw = payload.get("usage")
        if not isinstance(raw, dict):
            continue
        usage: dict[str, Any] = dict(raw)
        key = (str(usage.get("model_id", "")), str(usage.get("purpose", "action_planning")))
        into = totals.setdefault(key, {**usage, "context_tokens": 0, "input_tokens": 0,
                                       "output_tokens": 0, "duration_ms": 0})
        for name in ("context_tokens", "input_tokens", "output_tokens", "duration_ms"):
            into[name] += int(usage.get(name, 0))
        into["started_at"] = min(str(into["started_at"]), str(usage.get("started_at", "")))
    return [api.from_json(api.ModelUsage, data) for data in totals.values()]


def budget(conn: sqlite3.Connection, facts: RunFacts) -> api.BudgetState:
    cp, used = facts.checkpoint, facts.consumed
    return api.BudgetState(
        campaign_active_seconds=used.seconds + cp.active_seconds,
        campaign_pages=used.pages + cp.pages, campaign_states=len(cp.seen_keys),
        campaign_browser_actions=used.actions + cp.actions, campaign_cloud_eur=0.0,
        runs_used=max(1, len(delivery.run_ids(conn, facts.job_id))),
    )


def finished(
    conn: sqlite3.Connection,
    facts: RunFacts,
    scope: api.Scope,
    outcome: tuple[str, str, int],
    summary: api.FinishedPayloadFreshnessSummary,
) -> api.FinishedPayload:
    """outcome = (run_result_status, completion_reason, seq of this job.finished);
    summary = the counts of the run's contact.freshness checks."""
    result, reason, seq = outcome
    found = counts(conn, facts)
    return api.FinishedPayload(
        run_result_status=api.FinishedPayloadRunResultStatus(result),
        completion_reason=api.FinishedPayloadCompletionReason(reason),
        scope=scope, counts=found, coverage=coverage(facts, found.persons),
        checkpoint=server_checkpoint(facts), gaps=gaps(facts), last_content_seq=seq - 1,
        active_seconds=facts.checkpoint.active_seconds, wall_seconds=facts.wall_seconds,
        models=models_used(conn, facts.run_id), freshness_summary=summary,
        continuation_requested=result == service.PARTIAL and bool(facts.checkpoint.frontier),
        budget=budget(conn, facts),
    )


def attention(conn: sqlite3.Connection, facts: RunFacts) -> api.AttentionPayload:
    """job.needs_attention: the gap the owner has to solve (the last one) and the counts."""
    return api.AttentionPayload(gap=gaps(facts)[-1], counts=counts(conn, facts))


def progress(conn: sqlite3.Connection, facts: RunFacts, transport: str) -> api.ProgressPayload:
    found = counts(conn, facts)
    return api.ProgressPayload(
        stage=api.Stage(service.STAGE_BROWSER), counts=found,
        coverage=coverage(facts, found.persons), active_seconds=facts.checkpoint.active_seconds,
        transport_state=api.TransportState(transport),
    )
