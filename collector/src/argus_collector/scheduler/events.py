"""Contract events of a job run, built from walk findings with the generated types.

Every payload is an `api_client` dataclass (CLAUDE.md rule 14: the wire format
comes from the OpenAPI document only); `delivery.enqueue_event` adds the
envelope's event_id, seq and occurred_at.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from argus_collector.api_client import contract as api
from argus_collector.delivery.contract import MakeEvent
from argus_collector.models.contract import CallRecord
from argus_collector.scheduler import service
from argus_collector.walk import contract as walk

MIME_HTML = "text/html; charset=utf-8"
CHANNEL_FIELDS = ("phone", "email")


def envelope(cls: Callable[..., api.Event], job_id: str, run_id: str, payload: Any) -> MakeEvent:
    def make(event_id: str, seq: int, occurred_at: str) -> api.Event:
        return cls(
            event_id=event_id, job_id=job_id, run_id=run_id, seq=seq,
            occurred_at=occurred_at, payload=payload,
        )

    return make


def wire_evidence_id(job_id: str, run_id: str, sha256: str) -> str:
    """Evidence id sent to ARGUS: one per snapshot and run (uploads belong to a run)."""
    name = f"argus-collector:evidence:{job_id}:{run_id}:{sha256}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, name))


def started(job_id: str, run_id: str, version: str) -> MakeEvent:
    payload = api.StartedPayload(stage=api.Stage(service.STAGE_BROWSER), worker_version=version)
    return envelope(api.JobStartedEvent, job_id, run_id, payload)


def evidence_metadata(
    ids: tuple[str, str, str, str], source: walk.PageSource, version: str
) -> api.EvidenceMetadata:
    """ids = (wire evidence id, job_id, run_id, company_id)."""
    snapshot = source.snapshot
    return api.EvidenceMetadata(
        evidence_id=ids[0], job_id=ids[1], run_id=ids[2], company_id=ids[3],
        source_url=source.requested_url, final_url=source.url,
        source_kind=api.EvidenceMetadataSourceKind("browser_dom"), mime_type=MIME_HTML,
        fetched_at=snapshot.fetched_at, sha256=snapshot.html_sha256,
        byte_length=snapshot.html_bytes, capture_truncated=False, redacted=False,
        extractor_version=f"argus-collector {version}",
        canonical_text_sha256=snapshot.text_sha256, canonical_text=source.text,
    )


def source_event(
    kind: str, job_id: str, run_id: str, fields: tuple[str, str, str, str | None, str]
) -> Callable[[list[str]], MakeEvent]:
    """kind processed|blocked; fields = (source_id, url, state_key, parent, status)."""
    cls = api.SourceProcessedEvent if kind == "processed" else api.SourceBlockedEvent

    def with_evidence(evidence_ids: list[str], detail: str = "") -> MakeEvent:
        payload = api.SourcePayload(
            source_id=fields[0], url=fields[1], state_key=fields[2], parent_source_id=fields[3],
            status=fields[4], evidence_ids=evidence_ids, detail=detail,
        )
        return envelope(cls, job_id, run_id, payload)

    return with_evidence


def locator(found: walk.FieldFinding, text_sha256: str) -> api.Locator:
    if found.start >= 0:
        return api.LocatorTextSpan(start=found.start, end=found.end, text_sha256=text_sha256)
    if found.locator.startswith("jsonld:"):
        return api.LocatorJsonPointer(value="/" + found.locator.removeprefix("jsonld:"))
    if found.locator == "cfemail":
        return api.LocatorDom(value=f'[data-cfemail="{found.raw}"]', text_sha256=text_sha256)
    scheme = "tel" if found.field == "phone" else "mailto"
    return api.LocatorDom(value=f'a[href^="{scheme}:"]', text_sha256=text_sha256)


def observation(found: walk.FieldFinding, evidence_id: str, text_sha256: str) -> api.Observation:
    return api.Observation(
        observation_id=found.observation_id, field=found.field, raw_value=found.raw,
        normalized_value=found.value,
        extraction_status=api.ObservationExtractionStatus(found.status),
        evidence_id=evidence_id, locator=locator(found, text_sha256), quote=found.raw,
        binding=api.Binding(found.binding), change_kind=api.ObservationChangeKind("new"),
    )


def field_audit(evidence_id: str, entries: tuple[walk.AuditEntry, ...]) -> api.FieldAudit:
    items = [
        api.FieldAuditItem(
            source_field=e.source_field, disposition=api.FieldAuditItemDisposition("mapped"),
            observation_ids=list(e.observation_ids), raw_value=e.raw, reason="",
        )
        for e in entries
    ]
    return api.FieldAudit(evidence_id=evidence_id, items=items)


def contact(
    job_id: str, run_id: str, entity: walk.EntityFinding, evidence: tuple[str, str],
    audit: api.FieldAudit,
) -> MakeEvent:
    """contact.observed for a new entity, contact.enriched for new fields; evidence =
    (wire evidence id, canonical text sha256)."""
    relationship = None if entity.entity_type == "person" else "company"
    payload = api.ContactPayload(
        entity_id=entity.entity_id, entity_type=api.ContactPayloadEntityType(entity.entity_type),
        observations=[observation(f, evidence[0], evidence[1]) for f in entity.fields],
        field_audit=audit,
        relationship=api.ContactPayloadRelationship(relationship) if relationship else None,
    )
    cls = api.ContactObservedEvent if entity.is_new else api.ContactEnrichedEvent
    return envelope(cls, job_id, run_id, payload)


def model_usage(record: CallRecord) -> api.ModelUsage:
    return api.ModelUsage(
        model_id=record.model, provider="local", quantization=None,
        context_tokens=record.prompt_tokens + record.completion_tokens,
        input_tokens=record.prompt_tokens, output_tokens=record.completion_tokens,
        cost_eur=0.0, purpose=api.ModelUsagePurpose(service.purpose(record.purpose)),
        started_at=record.started_at, duration_ms=record.elapsed_ms, local=True,
    )


def model_called(
    job_id: str, run_id: str, record: CallRecord, source_id: str | None
) -> MakeEvent:
    payload = api.ModelCalledPayload(
        usage=model_usage(record), source_ids=[source_id] if source_id else []
    )
    return envelope(api.ModelCalledEvent, job_id, run_id, payload)
