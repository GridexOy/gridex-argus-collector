"""POST /jobs/{job_id}/reconcile: resume, drain_only and ownership."""

from __future__ import annotations

from contract_server.tests import payloads
from contract_server.tests.client import WORKER2_ID, WORKER2_TOKEN, WORKER_ID, Client
from contract_server.tests.conftest import FakeClock
from contract_server.tests.flow import Flow, Job
from contract_server.util import Json


def reconcile_body(
    job: Job,
    events: list[str] | None = None,
    evidence: list[str] | None = None,
    worker_id: str = WORKER_ID,
) -> Json:
    return {
        "worker_id": worker_id,
        "run_id": job.lease["run_id"],
        "last_acknowledged_seq": job.seq,
        "pending_event_ids": events or [],
        "pending_evidence_ids": evidence or [],
    }


def test_resume_after_expiry_keeps_run_and_seq(
    flow: Flow, client: Client, clock: FakeClock
) -> None:
    job = flow.start()
    evidence_id = flow.page(job, evidence_id="ev-1")
    started = flow.event(job, "job.started", payloads.started())
    flow.send(job, started)
    clock.advance(181)
    assert flow.job_status(job.job_id)["state"] == "queued"
    body = reconcile_body(job, [started["event_id"], "never-sent"], [evidence_id, "ev-missing"])
    status, result = client.post(f"/jobs/{job.job_id}/reconcile", body)
    assert status == 200
    assert result["mode"] == "resume"
    assert result["lease"]["run_id"] == job.lease["run_id"]
    assert result["lease"]["lease_generation"] == 2
    assert result["accepted_event_ids"] == [started["event_id"]]
    assert result["accepted_evidence_ids"] == ["ev-1"]
    assert result["missing_evidence_ids"] == ["ev-missing"]
    assert (result["last_contiguous_seq"], result["job_state"]) == (1, "leased")
    resumed = Job(job.job_id, job.company_id, result["lease"], seq=1)
    body2 = flow.send(resumed, flow.event(resumed, "job.progress", payloads.progress()))[1]
    assert (body2["results"][0]["status"], body2["last_contiguous_seq"]) == ("accepted", 2)


def test_resume_with_a_live_lease_rotates_the_token(flow: Flow, client: Client) -> None:
    job = flow.start()
    result = client.post(f"/jobs/{job.job_id}/reconcile", reconcile_body(job))[1]
    assert result["mode"] == "resume"
    assert result["lease"]["execution_token"] != job.token
    status, body = flow.send(job, flow.event(job, "job.started", payloads.started()))
    assert (status, body["code"]) == (409, "lease_mismatch")


def test_cancelled_job_gets_drain_only(flow: Flow, client: Client) -> None:
    job = flow.start()
    control = {"client_request_id": "x", "action": "cancel", "expected_state_revision": 0}
    client.system_post(f"/jobs/{job.job_id}/control", control)
    evidence_id = "ev-late"
    status, body = flow.upload(job, b"<p>+358 40 123 4567</p>", evidence_id=evidence_id)
    assert (status, body["code"]) == (409, "job_cancelled")
    result = client.post(f"/jobs/{job.job_id}/reconcile", reconcile_body(job))[1]
    assert (result["mode"], result["job_state"]) == ("drain_only", "cancelled")
    assert result["lease"]["lease_generation"] == 1
    assert result["lease"]["lease_expires_at"].startswith("2026-10-05T12:00:00")
    drain = result["lease"]["execution_token"]
    status, body = flow.upload(
        job, b"<p>+358 40 123 4567</p>", evidence_id=evidence_id, execution_token=drain
    )
    assert status == 201
    late = flow.contact(
        job, evidence_id, [payloads.observation("phone", "+358 40 123 4567", evidence_id)]
    )
    body = flow.send(job, late, token=drain)[1]
    assert (body["results"][0]["status"], body["results"][0]["state_applied"]) == (
        "accepted",
        False,
    )
    again = client.post(f"/jobs/{job.job_id}/reconcile", reconcile_body(job))[1]
    assert again["lease"]["execution_token"] == drain


def test_finished_run_gets_drain_only(flow: Flow, client: Client) -> None:
    job = flow.start()
    flow.finish(job, "completed")
    result = client.post(f"/jobs/{job.job_id}/reconcile", reconcile_body(job))[1]
    assert (result["mode"], result["job_state"]) == ("drain_only", "completed")
    assert result["last_contiguous_seq"] == 1


def test_only_the_pinned_worker_may_reconcile(flow: Flow, client: Client) -> None:
    job = flow.start()
    other = reconcile_body(job, worker_id=WORKER2_ID)
    status, body = client.post(f"/jobs/{job.job_id}/reconcile", other, token=WORKER2_TOKEN)
    assert (status, body["code"]) == (409, "lease_mismatch")
    spoofed = reconcile_body(job, worker_id=WORKER2_ID)
    status, body = client.post(f"/jobs/{job.job_id}/reconcile", spoofed)
    assert (status, body["code"]) == (409, "lease_mismatch")
    foreign = dict(reconcile_body(job), run_id="not-a-run")
    status, body = client.post(f"/jobs/{job.job_id}/reconcile", foreign)
    assert (status, body["code"]) == (409, "lease_mismatch")
    status, body = client.post("/jobs/missing/reconcile", reconcile_body(job))
    assert (status, body["code"]) == (404, "invalid_input")
