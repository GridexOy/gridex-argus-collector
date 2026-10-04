"""api_client operations against the embedded http.server double: paths, bodies, errors."""

from __future__ import annotations

import json
import socket
from collections.abc import Iterator

import pytest

from argus_collector.api_client import contract as api
from argus_collector.api_client.tests import samples, wire_samples
from argus_collector.api_client.tests.fake_argus import FakeArgus, parse_multipart

TOKEN = "worker-token"
CONTENT = b"\x00\xff<html>--argus-not-the-boundary\r\n\r\n</html>"


@pytest.fixture
def server() -> Iterator[FakeArgus]:
    srv = FakeArgus().start()
    try:
        yield srv
    finally:
        srv.stop()


def _claim_request() -> api.ClaimRequest:
    return api.ClaimRequest(worker_id="worker-1", max_jobs=8, capabilities=samples.capabilities())


def test_claim_jobs_posts_the_request_and_parses_every_job(server: FakeArgus) -> None:
    server.reply(200, wire_samples.CLAIM_RESPONSE)
    response = api.claim_jobs(server.base_url, TOKEN, _claim_request(), proxy_mode="direct")
    assert server.last.path == "/jobs/claim"
    assert server.last.headers["authorization"] == f"Bearer {TOKEN}"
    assert server.last.headers["content-type"] == "application/json"
    assert server.last.json() == api.to_json(_claim_request())
    assert server.last.json()["max_jobs"] == 8
    job = response.jobs[0]
    assert job.lease.execution_token == "exec-1"
    assert job.checkpoint is None
    assert job.job.scope.approved_hosts[0].basis is api.HostApprovalBasis.SEED
    assert job.job.participation_status is api.ParticipationStatus.CONFIRMED
    assert job.known_contacts[0].channel_status is api.ChannelStatus.PUBLISHED_DIRECT


def test_post_events_puts_the_quoted_job_id_in_the_path(server: FakeArgus) -> None:
    server.reply(200, wire_samples.EVENTS_RESPONSE)
    events: list[api.Event] = [samples.job_started(), samples.contact_observed()]
    request = api.EventsRequest(execution_token="exec-1", events=events)
    response = api.post_events(server.base_url, TOKEN, "job/1 x", request, proxy_mode="direct")
    assert server.last.path == "/jobs/job%2F1%20x/events"
    body = server.last.json()
    assert body["schema_version"] == "1.1"
    assert body["execution_token"] == "exec-1"
    assert [event["type"] for event in body["events"]] == ["job.started", "contact.observed"]
    assert body["events"][1]["payload"]["observations"][0]["locator"]["kind"] == "text_span"
    assert response.results[0].channel_status is None
    assert response.results[1].channel_status is api.ChannelStatus.PUBLISHED_DIRECT
    assert response.results[1].status is api.EventResultStatus.ACCEPTED
    assert response.job_state is api.JobState.RUNNING
    assert response.last_contiguous_seq == 3


def test_reconcile_job_returns_the_drain_only_lease(server: FakeArgus) -> None:
    server.reply(200, wire_samples.RECONCILE_RESPONSE)
    request = api.ReconcileRequest("worker-1", "run-1", 1, ["ev-2"], ["evd-2"])
    response = api.reconcile_job(server.base_url, TOKEN, "job-1", request, proxy_mode="direct")
    assert server.last.path == "/jobs/job-1/reconcile"
    assert server.last.json() == {
        "worker_id": "worker-1",
        "run_id": "run-1",
        "last_acknowledged_seq": 1,
        "pending_event_ids": ["ev-2"],
        "pending_evidence_ids": ["evd-2"],
    }
    assert response.mode is api.ReconcileResponseMode.DRAIN_ONLY
    assert response.lease.lease_generation == 2
    assert response.missing_evidence_ids == ["evd-2"]
    assert response.job_state is api.JobState.CANCELLED


@pytest.mark.parametrize("status", [201, 200])
def test_upload_evidence_sends_metadata_json_and_the_exact_bytes(
    server: FakeArgus, status: int
) -> None:
    server.reply(status, {**wire_samples.EVIDENCE_RESPONSE, "sha256": "f" * 64})
    metadata = samples.evidence_metadata(CONTENT)
    response = api.upload_evidence(
        server.base_url, TOKEN, "job-1", "exec-1", metadata, CONTENT,
        file_content_type="text/html", proxy_mode="direct",
    )  # fmt: skip
    sent = server.last
    assert sent.path == "/jobs/job-1/evidence"
    assert sent.headers["x-execution-token"] == "exec-1"
    assert sent.headers["authorization"] == f"Bearer {TOKEN}"
    parts = parse_multipart(sent.headers["content-type"], sent.body)
    assert list(parts) == ["metadata", "file"]
    meta_headers, meta_body = parts["metadata"]
    assert meta_headers["content-type"] == "application/json"
    assert "filename" not in meta_headers["content-disposition"]
    assert json.loads(meta_body) == api.to_json(metadata)
    file_headers, file_body = parts["file"]
    assert file_body == CONTENT
    assert file_headers["content-type"] == "text/html"
    assert file_headers["content-disposition"] == 'form-data; name="file"; filename="file"'
    assert response.status is api.EvidenceResponseStatus.ACCEPTED
    assert response.snapshot_id is None


def test_an_error_body_becomes_api_error_with_code_and_retry_after(server: FakeArgus) -> None:
    server.reply(429, wire_samples.ERROR, {"Retry-After": "5"})
    request = api.EventsRequest(execution_token="exec-1", events=[samples.job_started()])
    with pytest.raises(api.ApiError) as excinfo:
        api.post_events(server.base_url, TOKEN, "job-1", request, proxy_mode="direct")
    error = excinfo.value
    assert error.status == 429
    assert error.error is not None
    assert error.error.code == "sequence_gap"
    assert error.retry_after == "5"
    assert "sequence_gap" in error.raw


def test_a_2xx_body_of_the_wrong_shape_becomes_api_error(server: FakeArgus) -> None:
    server.reply(200, {"unexpected": True})
    request = api.ReconcileRequest("worker-1", "run-1", 0, [], [])
    with pytest.raises(api.ApiError) as excinfo:
        api.reconcile_job(server.base_url, TOKEN, "job-1", request, proxy_mode="direct")
    assert excinfo.value.status == 200
    assert excinfo.value.error is None


def test_a_refused_connection_is_status_0() -> None:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = int(probe.getsockname()[1])
    with pytest.raises(api.ApiError) as excinfo:
        api.claim_jobs(f"http://127.0.0.1:{port}", TOKEN, _claim_request(), proxy_mode="direct")
    assert excinfo.value.status == 0
    assert excinfo.value.error is None
