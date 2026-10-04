"""POST /jobs/claim: limits, atomicity, pinning, lease expiry and re-lease."""

from __future__ import annotations

import threading

from contract_server.tests import builders, payloads
from contract_server.tests.client import WORKER2_ID, WORKER2_TOKEN, WORKER_ID, WORKER_TOKEN, Client
from contract_server.tests.conftest import FakeClock
from contract_server.tests.flow import Flow, Job


def test_empty_queue_is_a_valid_claim(flow: Flow) -> None:
    assert flow.claim() == []


def test_claim_respects_max_jobs_and_creation_order(flow: Flow) -> None:
    flow.batch(*(builders.company(f"c{i}") for i in range(3)))
    first = flow.claim(max_jobs=2)
    assert [item["job"]["company_id"] for item in first] == ["c0", "c1"]
    second = flow.claim(max_jobs=2)
    assert [item["job"]["company_id"] for item in second] == ["c2"]
    assert flow.claim() == []


def test_claimed_job_carries_definition_lease_and_empty_extras(flow: Flow) -> None:
    flow.batch(builders.company("c1"))
    item = flow.claim()[0]
    assert item["job"]["schema_version"] == "1.1"
    assert item["job"]["policy"] == builders.POLICY
    assert item["lease"]["lease_generation"] == 1
    assert item["checkpoint"] is None
    assert (item["routes"], item["known_contacts"]) == ([], [])
    assert flow.job_status(item["job"]["job_id"])["state"] == "leased"


def test_claim_for_another_worker_id_is_invalid(client: Client) -> None:
    body = builders.claim_body(worker_id="someone-else")
    status, payload = client.post("/jobs/claim", body)
    assert (status, payload["code"]) == (400, "invalid_input")


def test_concurrent_claims_never_share_a_lease(flow: Flow) -> None:
    flow.batch(*(builders.company(f"c{i}") for i in range(8)))
    results: list[list[str]] = []

    def claim(token: str, worker_id: str) -> None:
        results.append([item["job"]["job_id"] for item in flow.claim(3, token, worker_id)])

    threads = [
        threading.Thread(target=claim, args=pair)
        for pair in [(WORKER_TOKEN, WORKER_ID), (WORKER2_TOKEN, WORKER2_ID)] * 2
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    claimed = [job_id for batch in results for job_id in batch]
    assert len(claimed) == len(set(claimed)) == 8


def test_job_stays_pinned_to_its_first_worker(flow: Flow, clock: FakeClock) -> None:
    job = flow.start()
    clock.advance(181)
    assert flow.claim(token=WORKER2_TOKEN, worker_id=WORKER2_ID) == []
    assert flow.job_status(job.job_id)["state"] == "queued"
    again = flow.claim()
    assert [item["job"]["job_id"] for item in again] == [job.job_id]


def test_expired_lease_requeues_and_reclaim_keeps_run_and_seq(flow: Flow, clock: FakeClock) -> None:
    job = flow.start()
    status, body = flow.send(job, flow.event(job, "job.started", payloads.started()))
    assert body["last_contiguous_seq"] == 1
    assert flow.job_status(job.job_id)["state"] == "running"
    clock.advance(181)
    assert flow.job_status(job.job_id)["state"] == "queued"
    item = flow.claim()[0]
    assert item["lease"]["run_id"] == job.lease["run_id"]
    assert item["lease"]["lease_generation"] == 2
    assert item["lease"]["execution_token"] != job.token
    status, body = flow.send(job, flow.event(job, "job.progress", payloads.progress()))
    assert (status, body["code"]) == (409, "lease_mismatch")
    renewed = Job(job.job_id, job.company_id, item["lease"], seq=1)
    status, body = flow.send(renewed, flow.event(renewed, "job.progress", payloads.progress()))
    assert status == 200
    assert body["results"][0]["status"] == "accepted"
    assert body["last_contiguous_seq"] == 2


def test_old_token_after_expiry_is_lease_expired(flow: Flow, clock: FakeClock) -> None:
    job = flow.start()
    clock.advance(200)
    status, body = flow.send(job, flow.event(job, "job.started", payloads.started()))
    assert (status, body["code"]) == (409, "lease_expired")


def test_paused_and_cancelled_jobs_are_not_claimed(flow: Flow, client: Client) -> None:
    created = flow.batch(builders.company("c1"), builders.company("c2"))
    first, second = (job["job_id"] for job in created["jobs"])
    for job_id, action in ((first, "pause"), (second, "cancel")):
        body = {"client_request_id": action, "action": action, "expected_state_revision": 0}
        status, _ = client.system_post(f"/jobs/{job_id}/control", body)
        assert status == 200
    assert flow.claim() == []
