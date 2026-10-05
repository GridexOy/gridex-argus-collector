"""needs_attention: the lease lives on, work resumes the job, control resume is allowed."""

from __future__ import annotations

import pytest

from contract_server.tests import builders, payloads
from contract_server.tests.client import Client
from contract_server.tests.conftest import FakeClock
from contract_server.tests.flow import Flow, Job
from contract_server.util import Json


def waiting(flow: Flow) -> Job:
    """A running job whose worker reported a bot check (job.needs_attention)."""
    job = flow.start()
    attention = {"gap": payloads.gap(), "counts": payloads.counts()}
    body = flow.send(
        job,
        flow.event(job, "job.started", payloads.started()),
        flow.event(job, "job.needs_attention", attention),
    )[1]
    assert body["job_state"] == "needs_attention"
    return job


def beat(client: Client, job: Job) -> Json:
    status, body = client.post(
        "/workers/heartbeat", builders.heartbeat_body([builders.active_lease(job.lease)])
    )
    assert status == 200, body
    renewal: Json = body["leases"][0]
    return renewal


def control(client: Client, job: Job, action: str) -> tuple[int, Json]:
    revision = client.get(f"/jobs/{job.job_id}")[1]["state_revision"]
    body = {
        "client_request_id": f"{action}-{revision}",
        "action": action,
        "expected_state_revision": revision,
    }
    return client.system_post(f"/jobs/{job.job_id}/control", body)


def test_heartbeat_keeps_the_lease_while_waiting(
    flow: Flow, client: Client, clock: FakeClock
) -> None:
    job = waiting(flow)
    for _ in range(3):
        clock.advance(170)
        assert beat(client, job)["status"] == "renewed"
    assert flow.job_status(job.job_id)["state"] == "needs_attention"
    body = flow.send(job, flow.event(job, "job.progress", payloads.progress()))[1]
    assert (body["results"][0]["status"], body["job_state"]) == ("accepted", "running")
    assert flow.job_status(job.job_id)["continuation"] == "none"


@pytest.mark.parametrize("kind", ["job.progress", "source.discovered", "contact.observed"])
def test_content_from_the_same_run_returns_to_running(flow: Flow, kind: str) -> None:
    job = waiting(flow)
    if kind == "contact.observed":
        ev = flow.page(job)
        event = flow.contact(job, ev, [payloads.observation("phone", "+358 40 123 4567", ev)])
    elif kind == "source.discovered":
        event = flow.event(job, kind, payloads.source())
    else:
        event = flow.event(job, kind, payloads.progress())
    assert flow.send(job, event)[1]["job_state"] == "running"


def test_other_events_keep_waiting(flow: Flow) -> None:
    job = waiting(flow)
    body = flow.send(job, flow.event(job, "model.called", payloads.model_called()))[1]
    assert body["job_state"] == "needs_attention"
    bad = flow.event(job, "job.progress", {"stage": "teleport"})
    assert flow.send(job, bad)[1]["job_state"] == "needs_attention"


def test_resume_from_needs_attention(flow: Flow, client: Client) -> None:
    job = waiting(flow)
    status, body = control(client, job, "resume")
    assert (status, body["state"], body["state_revision"]) == (200, "running", 1)
    commands = client.post("/workers/heartbeat", builders.heartbeat_body())[1]["commands"]
    assert [(c["action"], c["command_id"]) for c in commands] == [("resume", body["command_id"])]
    status, body = control(client, job, "resume")
    assert (status, body["code"]) == (409, "invalid_input")


def test_resume_without_a_live_lease_requeues(flow: Flow, client: Client, clock: FakeClock) -> None:
    job = waiting(flow)
    clock.advance(400)
    assert flow.job_status(job.job_id)["state"] == "needs_attention"
    assert control(client, job, "resume")[1]["state"] == "queued"
    item = flow.claim()[0]
    assert item["lease"]["run_id"] == job.lease["run_id"]
