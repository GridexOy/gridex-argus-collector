"""job.finished: sequence rule, job state, auto-continue and late deliveries."""

from __future__ import annotations

from contract_server.tests import builders, payloads
from contract_server.tests.client import Client
from contract_server.tests.flow import Flow, Job

AUTO = dict(builders.POLICY, auto_continue=True)


def test_finished_needs_last_content_seq(flow: Flow) -> None:
    job = flow.start()
    flow.send(job, flow.event(job, "job.started", payloads.started()))
    wrong = flow.event(job, "job.finished", payloads.finished(last_content_seq=0))
    body = flow.send(job, wrong)[1]
    assert (body["results"][0]["status"], body["results"][0]["code"]) == (
        "rejected",
        "sequence_gap",
    )
    assert (body["last_contiguous_seq"], body["job_state"]) == (1, "running")
    job.seq = 1
    status, body = flow.finish(job, "completed")
    assert status == 200
    assert body["results"][0]["status"] == "accepted"
    assert body["results"][0]["state_applied"] is True
    assert (body["job_state"], body["next_run_scheduled"]) == ("completed", False)


def test_finished_result_shows_in_job_status(flow: Flow) -> None:
    job = flow.start()
    gap = payloads.gap()
    flow.finish(job, "partial", gaps=[gap], coverage=payloads.coverage(gap_count=1))
    status = flow.job_status(job.job_id)
    assert (status["state"], status["runs_completed"]) == ("partial", 1)
    assert status["completion_reason"] == "budget_reached"
    assert status["gaps"] == [gap]
    assert status["coverage"]["gap_count"] == 1
    assert status["counts"]["gaps"] == 1
    assert (status["counts"]["browser_actions"], status["counts"]["states_processed"]) == (4, 2)
    assert status["budget"] == payloads.budget()
    assert status["continuation"] == "none"


def test_finished_replay_is_duplicate(flow: Flow) -> None:
    job = flow.start()
    finished = flow.event(job, "job.finished", payloads.finished(last_content_seq=0))
    first = flow.send(job, finished)[1]
    status, again = flow.send(job, finished)
    assert status == 200
    assert again["results"][0]["status"] == "duplicate"
    assert again["results"][0]["server_revision"] == first["results"][0]["server_revision"]


def test_auto_continue_schedules_the_next_run(flow: Flow) -> None:
    job = flow.start(policy=AUTO)
    body = flow.finish(job, "partial", continuation_requested=True)[1]
    assert (body["job_state"], body["next_run_scheduled"]) == ("queued", True)
    assert flow.job_status(job.job_id)["continuation"] == "scheduled"
    item = flow.claim()[0]
    assert item["lease"]["run_id"] != job.lease["run_id"]
    assert item["lease"]["lease_generation"] == 1
    assert item["checkpoint"] == payloads.checkpoint(pages=3)
    status = flow.job_status(job.job_id)
    assert (status["state"], status["continuation"], status["runs_completed"]) == (
        "leased",
        "none",
        1,
    )


def test_no_auto_continue_without_policy_or_request(flow: Flow) -> None:
    job = flow.start()
    body = flow.finish(job, "partial", continuation_requested=True)[1]
    assert (body["job_state"], body["next_run_scheduled"]) == ("partial", False)
    other = flow.start("c2", policy=AUTO)
    body = flow.finish(other, "partial", continuation_requested=False)[1]
    assert (body["job_state"], body["next_run_scheduled"]) == ("partial", False)


def test_exhausted_campaign_budget_stops_continuation(flow: Flow) -> None:
    job = flow.start(policy=dict(AUTO, max_runs=1))
    body = flow.finish(job, "partial", continuation_requested=True)[1]
    assert (body["job_state"], body["next_run_scheduled"]) == ("partial", False)
    assert flow.job_status(job.job_id)["continuation"] == "budget_exhausted"
    other = flow.start("c2", policy=AUTO)
    body = flow.finish(
        other, "partial", continuation_requested=True, budget=payloads.budget(pages=600)
    )[1]
    assert body["next_run_scheduled"] is False
    assert flow.job_status(other.job_id)["continuation"] == "budget_exhausted"


def test_late_finished_of_a_cancelled_job_does_not_apply(flow: Flow, client: Client) -> None:
    job = flow.start()
    flow.send(job, flow.event(job, "job.started", payloads.started()))
    control = {"client_request_id": "x", "action": "cancel", "expected_state_revision": 0}
    client.system_post(f"/jobs/{job.job_id}/control", control)
    status, body = flow.finish(job, "cancelled")
    assert (status, body["code"]) == (409, "job_cancelled")
    reconcile = {
        "worker_id": "worker-main-pc",
        "run_id": job.lease["run_id"],
        "last_acknowledged_seq": 1,
        "pending_event_ids": [],
        "pending_evidence_ids": [],
    }
    drain = client.post(f"/jobs/{job.job_id}/reconcile", reconcile)[1]
    assert drain["mode"] == "drain_only"
    job.seq = 1
    late = flow.event(job, "job.finished", payloads.finished(1, "cancelled"))
    body = flow.send(job, late, token=drain["lease"]["execution_token"])[1]
    assert body["results"][0]["status"] == "accepted"
    assert body["results"][0]["state_applied"] is False
    assert body["job_state"] == "cancelled"
    assert flow.job_status(job.job_id)["runs_completed"] == 1


def test_late_events_of_an_old_run_do_not_apply(flow: Flow, client: Client) -> None:
    job = flow.start()
    evidence_id = flow.page(job)
    old_token = job.token
    flow.finish(job, "partial")
    control = {"client_request_id": "c", "action": "continue", "expected_state_revision": 0}
    assert client.system_post(f"/jobs/{job.job_id}/control", control)[0] == 200
    item = flow.claim()[0]
    assert item["lease"]["run_id"] != job.lease["run_id"]
    old = Job(job.job_id, job.company_id, job.lease, seq=job.seq)
    late = flow.contact(
        old, evidence_id, [payloads.observation("phone", "+358 40 123 4567", evidence_id)]
    )
    body = flow.send(old, late, token=old_token)[1]
    assert body["results"][0]["status"] == "accepted"
    assert body["results"][0]["state_applied"] is False
    assert body["job_state"] == "leased"
    assert flow.job_status(job.job_id)["counts"]["persons"] == 1


def test_late_finished_of_an_old_run_is_accepted_without_effect(flow: Flow, client: Client) -> None:
    job = flow.start()
    flow.finish(job, "partial")
    control = {"client_request_id": "c", "action": "continue", "expected_state_revision": 0}
    client.system_post(f"/jobs/{job.job_id}/control", control)
    item = flow.claim()[0]
    late = flow.event(job, "job.finished", payloads.finished(job.seq, "completed"))
    body = flow.send(job, late)[1]
    assert (body["results"][0]["status"], body["results"][0]["state_applied"]) == (
        "accepted",
        False,
    )
    status = flow.job_status(job.job_id)
    assert (status["state"], status["current_run_id"]) == ("leased", item["lease"]["run_id"])
    assert (status["runs_completed"], status["completion_reason"]) == (1, "budget_reached")
