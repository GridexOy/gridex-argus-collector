"""GET /jobs/{id}, /batches/{id}, /workers/{id}/status: shapes, defaults and counts."""

from __future__ import annotations

from contract_server.tests import builders, payloads
from contract_server.tests.client import WORKER_ID, Client
from contract_server.tests.conftest import FakeClock
from contract_server.tests.flow import Flow

PHONE = "+358 40 123 4567"


def test_new_job_has_contract_defaults(flow: Flow) -> None:
    created = flow.batch(builders.company("c1", project_id=None))
    status = flow.job_status(created["jobs"][0]["job_id"])
    assert (status["state"], status["stage"], status["current_run_id"]) == ("queued", None, None)
    assert status["coverage"]["frontier_status"] == "not_started"
    assert status["coverage"]["expected_count"] is None
    assert status["counts"] == payloads.counts()
    assert (status["continuation"], status["runs_completed"]) == ("none", 0)
    assert (status["completion_reason"], status["last_result_at"]) == (None, None)
    assert status["budget"]["runs_used"] == 0
    assert (status["project_id"], status["transport_state"]) == (None, "synced")


def test_counts_follow_accepted_data(flow: Flow, clock: FakeClock) -> None:
    job = flow.start()
    evidence_id = flow.page(job)
    person = payloads.observation("phone", PHONE, evidence_id)
    org = payloads.observation("phone", "+358 9 555 0100", evidence_id, binding="caption")
    office = payloads.observation("email", "info@example.fi", evidence_id)
    clock.advance(5)
    flow.send(
        job,
        flow.event(job, "job.started", payloads.started()),
        flow.contact(job, evidence_id, [person]),
        flow.contact(job, evidence_id, [org], entity_type="organization_channel", entity_id="o"),
        flow.contact(job, evidence_id, [office], entity_type="office", entity_id="f"),
        flow.event(job, "source.processed", payloads.source([evidence_id])),
        flow.event(job, "job.progress", payloads.progress(browser_actions=7, states_processed=3)),
    )
    status = flow.job_status(job.job_id)
    counts = status["counts"]
    assert (counts["persons"], counts["organization_channels"], counts["other_entities"]) == (
        1,
        1,
        1,
    )
    assert (counts["observations"], counts["pages_processed"], counts["evidence_count"]) == (
        3,
        1,
        1,
    )
    assert (counts["browser_actions"], counts["states_processed"]) == (7, 3)
    assert (status["state"], status["stage"]) == ("running", "browser")
    assert status["coverage"]["frontier_status"] == "partial"
    assert status["current_run_id"] == job.lease["run_id"]
    assert status["last_result_at"].startswith("2026-10-04T12:00:05")


def test_transport_state_tracks_the_worker(flow: Flow, client: Client, clock: FakeClock) -> None:
    job = flow.start()
    assert flow.job_status(job.job_id)["transport_state"] == "offline"
    client.post("/workers/heartbeat", builders.heartbeat_body(outbox_pending=2))
    assert flow.job_status(job.job_id)["transport_state"] == "syncing"
    assert flow.job_status(job.job_id)["counts"]["outbox_pending"] == 2
    client.post("/workers/heartbeat", builders.heartbeat_body())
    assert flow.job_status(job.job_id)["transport_state"] == "synced"
    clock.advance(91)
    assert flow.job_status(job.job_id)["transport_state"] == "offline"


def test_batch_status_lists_job_statuses(flow: Flow, client: Client) -> None:
    created = flow.batch(builders.company("c1"), builders.company("c2"))
    status, batch = client.get(f"/batches/{created['batch_id']}")
    assert status == 200
    assert batch["batch_id"] == created["batch_id"]
    assert [job["company_id"] for job in batch["jobs"]] == ["c1", "c2"]


def test_never_seen_worker_has_defaults(client: Client) -> None:
    status, worker = client.get(f"/workers/{WORKER_ID}/status")
    assert status == 200
    assert (worker["connected"], worker["last_seen_at"], worker["worker_version"]) == (
        False,
        None,
        "",
    )
    assert worker["capabilities"]["release_level"] == "M1"
    assert not any(worker["capabilities"][key] for key in ("http", "browser", "vision", "model"))
    assert worker["transport_state"] == "offline"


def test_worker_status_after_heartbeat_and_timeout(
    flow: Flow, client: Client, clock: FakeClock
) -> None:
    flow.batch(builders.company("c1"), builders.company("c2"))
    client.post("/workers/heartbeat", builders.heartbeat_body())
    worker = client.get(f"/workers/{WORKER_ID}/status")[1]
    assert (worker["connected"], worker["collecting"], worker["queued_jobs"]) == (True, True, 2)
    assert worker["worker_version"] == "0.4.2.0"
    assert worker["capabilities"] == builders.capabilities()
    assert worker["last_seen_at"].startswith("2026-10-04T12:00:00")
    flow.claim(max_jobs=1)
    assert client.get(f"/workers/{WORKER_ID}/status")[1]["queued_jobs"] == 1
    clock.advance(91)
    worker = client.get(f"/workers/{WORKER_ID}/status")[1]
    assert (worker["connected"], worker["transport_state"]) == (False, "offline")


def test_needs_attention_waits_for_attention(flow: Flow) -> None:
    job = flow.start()
    attention = {"gap": payloads.gap(), "counts": payloads.counts()}
    flow.send(
        job,
        flow.event(job, "job.started", payloads.started()),
        flow.event(job, "job.needs_attention", attention),
    )
    status = flow.job_status(job.job_id)
    assert (status["state"], status["continuation"]) == ("needs_attention", "waiting_attention")
