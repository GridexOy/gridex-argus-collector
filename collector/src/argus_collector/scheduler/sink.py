"""The walk sink of a job run: walk findings -> outbox events + local counters."""

from __future__ import annotations

import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from argus_collector.api_client import contract as api
from argus_collector.delivery import contract as delivery
from argus_collector.models.contract import CallRecord
from argus_collector.runtime import contract as runtime
from argus_collector.scheduler import events, finish, history, service
from argus_collector.scheduler import repository as repo
from argus_collector.storage import contract as storage
from argus_collector.walk import contract as walk

PROGRESS_EVERY_S = 15.0


@dataclass(frozen=True)
class RunContext:
    job_id: str
    run_id: str
    company_id: str
    version: str
    hosts: tuple[str, ...]
    consumed: service.Consumed
    started_at: datetime  # when the run was claimed (wall time of job.finished)
    known: tuple[history.Known, ...] = ()  # ClaimedJob.known_contacts (a re-run)


class JobSink:
    """`walk.WalkSink` of one run; `transport()` gives the delivery state for job.progress."""

    def __init__(self, ctx: RunContext, transport: Callable[[], str]) -> None:
        self.ctx = ctx
        self.transport = transport
        self.source_id: str | None = None
        self._last_progress = 0.0
        self.known = history.KnownIndex(list(ctx.known))

    def _wire(self, source: walk.PageSource) -> str:
        sha = source.snapshot.html_sha256
        return events.wire_evidence_id(self.ctx.job_id, self.ctx.run_id, sha)

    def _enqueue(self, conn: sqlite3.Connection, make: delivery.MakeEvent, ids: list[str]) -> None:
        delivery.enqueue_event(conn, self.ctx.job_id, self.ctx.run_id, make, ids)

    def page_stored(self, conn: sqlite3.Connection, source: walk.PageSource) -> None:
        ctx = self.ctx
        ids = (self._wire(source), ctx.job_id, ctx.run_id, ctx.company_id)
        metadata = events.evidence_metadata(ids, source, ctx.version)
        with storage.transaction(conn):
            if delivery.enqueue_evidence(conn, source.snapshot.evidence_id, metadata):
                repo.bump_job_tx(conn, ctx.job_id, sources=1)
        self.source_id = source.source_id
        runtime.journal("browser", f"job {ctx.job_id}: page {runtime.safe_url(source.url)}")

    def page_done(self, conn: sqlite3.Connection, found: walk.PageFindings) -> None:
        """Inside the walk's transaction (with the local observation rows)."""
        ctx, source = self.ctx, found.source
        wire = self._wire(source)
        audit = events.field_audit(wire, found.audit)
        fields = 0
        for entity in found.entities:
            evidence = (wire, source.snapshot.text_sha256)
            change = self._change_of(entity)
            self._enqueue(conn, events.contact(ctx.job_id, ctx.run_id, entity, evidence, audit,
                                               change), [wire])
            fields += len(entity.fields)
            self._count(conn, entity)
        fields_of = (source.source_id, source.url, source.state_key, source.parent_source_id,
                     "extracted")
        processed = events.source_event("processed", ctx.job_id, ctx.run_id, fields_of)
        self._enqueue(conn, processed([wire]), [wire])
        runtime.journal(
            "extraction",
            f"job {ctx.job_id}: {len(found.entities)} entities, {fields} new fields,"
            f" {len(found.audit)} audited fields on {runtime.safe_url(source.url)}",
        )

    def _change_of(self, entity: walk.EntityFinding) -> events.Change:
        values: dict[str, set[str]] = {}
        for f in entity.fields:
            values.setdefault(f.field, set()).add(f.value)
        known = self.known.match(entity.entity_type, entity.entity_key, values)
        return lambda f: self.known.change(known, f.field, f.value)

    def _count(self, conn: sqlite3.Connection, entity: walk.EntityFinding) -> None:
        ctx = self.ctx
        new = repo.map_entity_tx(
            conn, ctx.job_id, entity.entity_key, (entity.entity_id, entity.entity_type), ctx.run_id
        )
        channels = sum(1 for f in entity.fields if f.field in events.CHANNEL_FIELDS)
        persons = 1 if new and entity.entity_type == "person" else 0
        repo.bump_job_tx(
            conn, ctx.job_id, persons=persons, channels=channels, observations=len(entity.fields)
        )

    def gap(self, conn: sqlite3.Connection, gap: walk.WalkGap) -> None:
        ctx = self.ctx
        fields = (f"gap:{gap.state_key}:{gap.reason}", gap.url, gap.state_key, self.source_id,
                  gap.reason)
        blocked = events.source_event("blocked", ctx.job_id, ctx.run_id, fields)
        with storage.transaction(conn):
            self._enqueue(conn, blocked([]), [])
        runtime.journal(
            "browser", f"job {ctx.job_id}: gap {gap.reason} at {runtime.safe_url(gap.url)}"
        )

    def model_called(self, conn: sqlite3.Connection, record: CallRecord) -> None:
        ctx = self.ctx
        with storage.transaction(conn):
            self._enqueue(conn, events.model_called(ctx.job_id, ctx.run_id, record,
                                                    self.source_id), [])
        runtime.journal(
            "model",
            f"job {ctx.job_id}: {record.purpose} {record.model} in={record.prompt_tokens}"
            f" out={record.completion_tokens} {record.elapsed_ms} ms ok={record.ok} cost_eur=0",
        )

    def checkpoint(self, conn: sqlite3.Connection, checkpoint: walk.WalkCheckpoint) -> None:
        ctx = self.ctx
        with storage.transaction(conn):
            repo.save_checkpoint_tx(conn, ctx.run_id, ctx.job_id, checkpoint.to_json())
            if time.monotonic() - self._last_progress >= PROGRESS_EVERY_S:
                self._last_progress = time.monotonic()
                facts = self.facts(checkpoint, "")
                payload = finish.progress(conn, facts, self.transport())
                make = events.envelope(api.JobProgressEvent, ctx.job_id, ctx.run_id, payload)
                self._enqueue(conn, make, [])

    def facts(self, checkpoint: walk.WalkCheckpoint, end_reason: str) -> finish.RunFacts:
        ctx = self.ctx
        wall = max(0.0, (datetime.now(UTC) - ctx.started_at).total_seconds())
        return finish.RunFacts(
            ctx.job_id, ctx.run_id, ctx.hosts, end_reason, checkpoint, ctx.consumed, wall
        )
