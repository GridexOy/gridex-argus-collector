"""Sample api_client values shared by the tests (hand-written, test-only)."""

from __future__ import annotations

import hashlib
import importlib
from collections.abc import Callable
from pathlib import Path
from typing import Any

from argus_collector.api_client import contract as api

AT = "2026-10-04T12:00:00Z"
SHA = "a" * 64
PACKAGE_DIR = Path(__file__).resolve().parents[1]


def codec(name: str) -> Callable[..., Any]:
    """A generated `<snake>_to_json`/`_from_json`, wherever the chunking placed it."""
    for path in sorted(PACKAGE_DIR.glob("serialization_*.py")):
        module = importlib.import_module(f"argus_collector.api_client.{path.stem}")
        found = getattr(module, name, None)
        if callable(found):
            return found  # type: ignore[no-any-return]
    raise LookupError(name)


def envelope(seq: int) -> dict[str, Any]:
    """The fields every Event variant shares (the const `type`/`schema_version` excluded)."""
    return {"event_id": f"ev-{seq}", "job_id": "job-1", "run_id": "run-1", "seq": seq} | {
        "occurred_at": AT
    }


def capabilities() -> api.Capabilities:
    return api.Capabilities(True, True, False, True, ["pdf"], api.CapabilitiesReleaseLevel.M1)


def observation() -> api.Observation:
    return api.Observation(
        observation_id="obs-1",
        field="email",
        raw_value="Matti@Example.fi ",
        normalized_value="matti@example.fi",
        extraction_status=api.ObservationExtractionStatus.CONFIRMED,
        evidence_id="evd-1",
        locator=api.LocatorTextSpan(start=10, end=26, text_sha256=SHA),
        quote="Matti@Example.fi",
        binding=api.Binding.CARD,
    )


def contact_observed() -> api.ContactObservedEvent:
    item = api.FieldAuditItem(
        "email", api.FieldAuditItemDisposition.MAPPED, ["obs-1"], "Matti@Example.fi ", "email"
    )
    payload = api.ContactPayload(
        entity_id="ent-1",
        entity_type=api.ContactPayloadEntityType.PERSON,
        observations=[observation()],
        field_audit=api.FieldAudit(evidence_id="evd-1", items=[item]),
        relationship=api.ContactPayloadRelationship.EMPLOYEE,
    )
    return api.ContactObservedEvent(**envelope(3), payload=payload)


def scope() -> api.Scope:
    host = api.HostApproval("example.fi", api.HostApprovalBasis.SEED, None)
    return api.Scope(api.ScopeGeography.ALL_PUBLISHED, ["FI"], ["fi", "en"], [host], True, False)


def counts() -> api.Counts:
    return api.Counts(3, 1, 0, 9, 12, 4, 7, 1, 0, 15)


def checkpoint() -> api.Checkpoint:
    item = api.FrontierItem(
        "src-2", "https://example.fi/staff?page=2", "staff#2", "src-1", 5,
        api.FrontierItemMethod.BROWSER, "queued", {"letter": "A"}, None, 1, None,
    )  # fmt: skip
    return api.Checkpoint([item], "evd-ckpt", ["route-1"], 12.5, 12, 4)


def usage() -> api.ModelUsage:
    return api.ModelUsage(
        "qwen3-8b", "llama.cpp", None, 8192, 1200, 80, 0.0,
        api.ModelUsagePurpose.CARD_PARSING, AT, 950, True,
    )  # fmt: skip


def job_finished() -> api.JobFinishedEvent:
    coverage = api.Coverage(
        api.CoverageFrontierStatus.EXHAUSTED, api.CoverageConfirmation.UNVERIFIED,
        api.CoverageBasis.FRONTIER_EXHAUSTED, "staff pages of example.fi", None, 3, 1, ["evd-1"],
    )  # fmt: skip
    gap = api.Gap("gap-1", "https://example.fi/x", "x#0", api.GapReason.CAPTCHA, "captcha", 2, True)
    payload = api.FinishedPayload(
        run_result_status=api.FinishedPayloadRunResultStatus.COMPLETED,
        completion_reason=api.FinishedPayloadCompletionReason.FRONTIER_EXHAUSTED,
        scope=scope(),
        counts=counts(),
        coverage=coverage,
        checkpoint=checkpoint(),
        gaps=[gap],
        last_content_seq=3,
        active_seconds=12.5,
        wall_seconds=30.0,
        models=[usage()],
        freshness_summary=api.FinishedPayloadFreshnessSummary(1, 0, 0, 2),
        continuation_requested=False,
        budget=api.BudgetState(12.5, 12, 15, 4, 0.0, 1),
    )
    return api.JobFinishedEvent(**envelope(4), payload=payload)


def model_called() -> api.ModelCalledEvent:
    payload = api.ModelCalledPayload(usage=usage(), source_ids=["src-1"])
    return api.ModelCalledEvent(**envelope(2), payload=payload)


def job_started() -> api.JobStartedEvent:
    payload = api.StartedPayload(stage=api.Stage.HTTP, worker_version="0.5.0.0")
    return api.JobStartedEvent(**envelope(1), payload=payload)


def route() -> api.Route:
    step = api.RouteStep(api.RouteStepAction.CLICK, "Henkilokunta", "link", None, None, "list")
    return api.Route(
        "route-1", "example.fi", api.RoutePurpose.CONTACT_INDEX, "https://example.fi/",
        [step], api.RouteSignature(None, 12), api.RouteStatus.ACTIVE, 3, 0, None,
    )  # fmt: skip


def route_recorded() -> api.RouteRecordedEvent:
    payload = api.RouteRecordedPayload(route=route(), evidence_ids=["evd-1"])
    return api.RouteRecordedEvent(**envelope(5), payload=payload)


def job_progress() -> api.JobProgressEvent:
    coverage = api.Coverage(
        api.CoverageFrontierStatus.PARTIAL, api.CoverageConfirmation.UNVERIFIED,
        api.CoverageBasis.UNKNOWN, "staff", None, 1, 0, [],
    )  # fmt: skip
    payload = api.ProgressPayload(
        api.Stage.BROWSER, counts(), coverage, 4.0, api.TransportState.SYNCING
    )
    return api.JobProgressEvent(**envelope(6), payload=payload)


def evidence_metadata(content: bytes) -> api.EvidenceMetadata:
    return api.EvidenceMetadata(
        evidence_id="evd-1",
        job_id="job-1",
        run_id="run-1",
        company_id="company-1",
        source_url="https://example.fi/staff",
        final_url="https://example.fi/staff/",
        source_kind=api.EvidenceMetadataSourceKind.HTTP_HTML,
        mime_type="text/html",
        fetched_at=AT,
        sha256=hashlib.sha256(content).hexdigest(),
        byte_length=len(content),
        capture_truncated=False,
        redacted=False,
        extractor_version="0.5.0",
    )
