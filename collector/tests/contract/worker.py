"""Worker-side calls of the contract tests, built only with the generated client."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from argus_collector.api_client import contract as api

if TYPE_CHECKING:
    from collector.tests.contract.conftest import Argus

HTML = "<html><body><p>Anna Virtanen</p><p>Myyntijohtaja</p><p>040 123 4567</p></body></html>"
TEXT = "Anna Virtanen\nMyyntijohtaja\n040 123 4567"
CAPS = api.Capabilities(http=True, browser=True, vision=False, model=True, document_formats=[],
                        release_level=api.CapabilitiesReleaseLevel("M1"))


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def claim(argus: Argus, max_jobs: int = 8) -> list[api.ClaimedJob]:
    request = api.ClaimRequest(worker_id=argus.worker_id, max_jobs=max_jobs, capabilities=CAPS)
    return api.claim_jobs(argus.base_url, argus.token, request, proxy_mode=_mode(argus)).jobs


def _mode(argus: Argus) -> api.ProxyMode:
    return "direct" if argus.proxy == "direct" else "system"


def upload(
    argus: Argus, claimed: api.ClaimedJob, final_url: str = "", evidence_id: str = ""
) -> api.EvidenceResponse:
    job, lease = claimed.job, claimed.lease
    metadata = api.EvidenceMetadata(
        evidence_id=evidence_id or str(uuid.uuid4()), job_id=job.job_id, run_id=lease.run_id,
        company_id=job.company_id, source_url=job.seed_urls[0],
        final_url=final_url or job.seed_urls[0],
        source_kind=api.EvidenceMetadataSourceKind("browser_dom"), mime_type="text/html",
        fetched_at=now(), sha256=sha(HTML), byte_length=len(HTML.encode("utf-8")),
        capture_truncated=False, redacted=False, extractor_version="contract-tests",
        canonical_text_sha256=sha(TEXT), canonical_text=TEXT,
    )
    return api.upload_evidence(argus.base_url, argus.token, job.job_id, lease.execution_token,
                               metadata, HTML.encode("utf-8"), file_content_type="text/html",
                               proxy_mode=_mode(argus))


def phone_contact(
    claimed: api.ClaimedJob, seq: int, evidence_id: str, audit: bool = True
) -> api.ContactObservedEvent:
    start = TEXT.index("040 123 4567")
    observation = api.Observation(
        observation_id=str(uuid.uuid4()), field="phone", raw_value="040 123 4567",
        normalized_value="+358401234567",
        extraction_status=api.ObservationExtractionStatus("confirmed"), evidence_id=evidence_id,
        locator=api.LocatorTextSpan(start=start, end=start + 12, text_sha256=sha(TEXT)),
        quote="040 123 4567", binding=api.Binding("card"),
    )
    item = api.FieldAuditItem(source_field="phone", disposition=api.FieldAuditItemDisposition(
        "mapped"), observation_ids=[observation.observation_id], raw_value="040 123 4567",
        reason="")
    field_audit = api.FieldAudit(evidence_id=evidence_id, items=[item] if audit else [])
    payload = api.ContactPayload(entity_id=str(uuid.uuid4()),
                                 entity_type=api.ContactPayloadEntityType("person"),
                                 observations=[observation], field_audit=field_audit)
    return api.ContactObservedEvent(event_id=str(uuid.uuid4()), job_id=claimed.job.job_id,
                                    run_id=claimed.lease.run_id, seq=seq, occurred_at=now(),
                                    payload=payload)


def started(claimed: api.ClaimedJob, seq: int) -> api.JobStartedEvent:
    payload = api.StartedPayload(stage=api.Stage("browser"), worker_version="contract-tests")
    return api.JobStartedEvent(event_id=str(uuid.uuid4()), job_id=claimed.job.job_id,
                               run_id=claimed.lease.run_id, seq=seq, occurred_at=now(),
                               payload=payload)


def post(
    argus: Argus, claimed: api.ClaimedJob, events: list[Any], token: str = ""
) -> api.EventsResponse:
    request = api.EventsRequest(execution_token=token or claimed.lease.execution_token,
                                events=events)
    return api.post_events(argus.base_url, argus.token, claimed.job.job_id, request,
                           proxy_mode=_mode(argus))


def without_audit(event: api.ContactObservedEvent) -> dict[str, Any]:
    """The same event on the wire without `field_audit` (a worker bug the server catches)."""
    data = api.to_json(event)
    del data["payload"]["field_audit"]
    return data


def post_raw(argus: Argus, job_id: str, body: dict[str, Any]) -> tuple[int, Any]:
    """Events request as raw JSON (for payloads the typed client cannot even build)."""
    import json  # noqa: PLC0415 - only this helper needs it
    import urllib.error  # noqa: PLC0415
    import urllib.request  # noqa: PLC0415

    req = urllib.request.Request(
        f"{argus.base_url}/jobs/{job_id}/events", data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {argus.token}", "Content-Type": "application/json"},
        method="POST",
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read().decode("utf-8") or "{}")
