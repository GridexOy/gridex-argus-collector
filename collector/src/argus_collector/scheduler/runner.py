"""One job run: job.started, the walk with the job's scope and budget, job.finished."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from argus_collector.api_client import contract as api
from argus_collector.delivery import contract as delivery
from argus_collector.discovery import contract as discovery
from argus_collector.models.contract import ModelConfig
from argus_collector.runtime import contract as runtime
from argus_collector.scheduler import events, finish, freshness, history, service
from argus_collector.scheduler import repository as repo
from argus_collector.scheduler.sink import JobSink, RunContext
from argus_collector.storage import contract as storage
from argus_collector.walk import contract as walk

DEFAULT_REGION = "FI"


@dataclass(frozen=True)
class WalkEnv:
    """The machine side of a walk (same for every job)."""

    model: ModelConfig
    headless: bool
    profile_dir: Path | None
    evidence_dir: Path | None
    db_path: Path | None
    stop_files: tuple[Path, ...]
    version: str


def claimed_job(row: sqlite3.Row) -> api.ClaimedJob:
    return api.from_json(api.ClaimedJob, json.loads(row["definition_json"]))


def host_key(host: str) -> str:
    """Approved host as the walk compares it: lower case, no `www.`, no port."""
    bare = host.strip().lower()
    if "://" in bare:
        bare = urlsplit(bare).hostname or ""
    bare = bare.split("/", 1)[0].split(":", 1)[0]
    return bare[4:] if bare.startswith("www.") else bare


def consumed(claimed: api.ClaimedJob) -> service.Consumed:
    cp = claimed.checkpoint
    if cp is None:
        return service.Consumed()
    return service.Consumed(cp.active_seconds_consumed, cp.pages_consumed, cp.actions_consumed)


def resume_checkpoint(
    conn: sqlite3.Connection, row: sqlite3.Row, claimed: api.ClaimedJob
) -> walk.WalkCheckpoint | None:
    """Same run: its own checkpoint. New run of the job: the previous run's knowledge
    (visited, entities, ids) with fresh counters, else the server's frontier."""
    own = repo.checkpoint(conn, row["run_id"])
    if own is not None:
        return walk.WalkCheckpoint.from_json(own)
    earlier = repo.latest_checkpoint(conn, row["job_id"])
    if earlier is not None:
        cp = walk.WalkCheckpoint.from_json(earlier)
        return replace(cp, last_url="", gaps=[], pages=0, actions=0, active_seconds=0.0)
    if claimed.checkpoint is None or not claimed.checkpoint.frontier_items:
        return None
    links = {
        item.state_key: walk.FrontierLink(item.url, "", item.priority, "")
        for item in claimed.checkpoint.frontier_items
    }
    return walk.WalkCheckpoint(frontier=links)


def walk_settings(
    env: WalkEnv, claimed: api.ClaimedJob, resume: walk.WalkCheckpoint | None
) -> walk.WalkSettings:
    job = claimed.job
    scope = job.scope
    hosts = frozenset(host_key(h.host) for h in scope.approved_hosts)
    countries = list(scope.priority_countries)
    focus = discovery.make_focus(countries, list(scope.priority_languages))
    if focus is not None:
        focus = replace(focus, local_seed=discovery.is_local_seed(job.seed_urls[0], focus.country))
    return walk.WalkSettings(
        start_url=job.seed_urls[0], model=env.model, headless=env.headless,
        profile_dir=env.profile_dir, evidence_dir=env.evidence_dir, db_path=env.db_path,
        stop_files=env.stop_files, approved_hosts=hosts,
        focus=focus,
        limits=service.run_limits(api.to_json(job.policy), consumed(claimed)),
        resume=resume, id_namespace=job.job_id,
        region_fallback=countries[0].upper() if countries else DEFAULT_REGION,
    )


def context(row: sqlite3.Row, claimed: api.ClaimedJob, env: WalkEnv) -> RunContext:
    hosts = tuple(sorted(host_key(h.host) for h in claimed.job.scope.approved_hosts))
    return RunContext(
        row["job_id"], row["run_id"], row["company_id"], env.version, hosts, consumed(claimed),
        datetime.fromisoformat(row["claimed_at"]),
        tuple(history.parse_known(claimed.known_contacts)),
    )


def begin(conn: sqlite3.Connection, row: sqlite3.Row, version: str) -> None:
    """job.started once per run; the job is `running` in stage `browser`."""
    with storage.transaction(conn):
        if not row["started"]:
            make = events.started(row["job_id"], row["run_id"], version)
            delivery.enqueue_event(conn, row["job_id"], row["run_id"], make, [])
        repo.update_job_tx(conn, row["job_id"], state=service.RUNNING,
                           stage=service.STAGE_BROWSER, started=1)


def finish_run(
    conn: sqlite3.Connection,
    row: sqlite3.Row,
    env: WalkEnv,
    checkpoint: walk.WalkCheckpoint,
    ending: tuple[str, bool],
) -> str:
    """Enqueue job.finished once per run; ending = (walk end reason, cancelled)."""
    current = repo.job(conn, row["job_id"])
    if current is None or current["finished"]:
        return current["state"] if current else service.FAILED
    claimed = claimed_job(row)
    end_reason, cancelled = ending
    found = int(current["persons"]) + int(current["channels"]) > 0
    result, reason = service.outcome(end_reason, found, cancelled)
    facts = JobSink(context(row, claimed, env), lambda: "synced").facts(checkpoint, end_reason)
    ids = (row["job_id"], row["run_id"])
    cover = finish.coverage(facts, finish.counts(conn, facts).persons)
    checks = freshness.checks(conn, ids, claimed.known_contacts, checkpoint, cover)
    with storage.transaction(conn):
        freshness.enqueue_tx(conn, ids, checks)
        seq = delivery.next_seq(conn, row["run_id"])
        payload = finish.finished(
            conn, facts, claimed.job.scope, (result, reason, seq), freshness.summary(checks)
        )
        make = events.envelope(api.JobFinishedEvent, row["job_id"], row["run_id"], payload)
        delivery.enqueue_event(conn, row["job_id"], row["run_id"], make, [], seq=seq)
        repo.update_job_tx(conn, row["job_id"], state=result, stage=service.STAGE_FINALIZING,
                           finished=1, result_status=result, completion_reason=reason)
    runtime.journal("browser", f"job {row['job_id']}: finished {result} ({reason}), seq {seq}")
    return result


def needs_attention(
    conn: sqlite3.Connection, row: sqlite3.Row, env: WalkEnv, checkpoint: walk.WalkCheckpoint
) -> str:
    """job.needs_attention once; the run stays open until the owner presses Jatka."""
    facts = JobSink(context(row, claimed_job(row), env), lambda: "synced").facts(
        checkpoint, walk.END_ATTENTION
    )
    with storage.transaction(conn):
        payload = finish.attention(conn, facts)
        make = events.envelope(api.JobNeeds_AttentionEvent, row["job_id"], row["run_id"], payload)
        delivery.enqueue_event(conn, row["job_id"], row["run_id"], make, [])
        repo.update_job_tx(conn, row["job_id"], state=service.NEEDS_ATTENTION,
                           stage=service.STAGE_QUEUED, detail=payload.gap.source_url)
    runtime.journal("browser", f"job {row['job_id']}: needs attention ({payload.gap.reason.value})")
    return service.NEEDS_ATTENTION


def run_job(
    conn: sqlite3.Connection,
    row: sqlite3.Row,
    env: WalkEnv,
    hooks: tuple[Callable[[], bool], Callable[[walk.WalkEvent], None], Callable[[], str]],
    interrupt_of: Callable[[], str | None],
) -> str:
    """Walk the job; returns its new local state. hooks = (should_stop, on_event, transport)."""
    should_stop, on_event, transport = hooks
    claimed = claimed_job(row)
    begin(conn, row, env.version)
    sink = JobSink(context(row, claimed, env), transport)
    settings = walk_settings(env, claimed, resume_checkpoint(conn, row, claimed))
    summary = walk.run_walk(settings, on_event, should_stop, sink)
    reason = interrupt_of() or (service.STOP_COLLECTING if summary.stopped else None)
    if reason in (service.STOP_COLLECTING, service.STOP_PAUSE, service.STOP_LEASE):
        state = {service.STOP_COLLECTING: service.STOPPED, service.STOP_PAUSE: service.PAUSED,
                 service.STOP_LEASE: service.WAITING_LEASE}[reason]
        repo.update_job(conn, row["job_id"], state=state, stage=service.STAGE_QUEUED)
        return state
    if reason is None and summary.end_reason == walk.END_ATTENTION:
        return needs_attention(conn, row, env, summary.checkpoint)
    cancelled = reason == service.STOP_CANCEL
    return finish_run(conn, row, env, summary.checkpoint, (summary.end_reason, cancelled))
