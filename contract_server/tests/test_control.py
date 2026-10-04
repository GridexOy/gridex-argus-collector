"""POST /jobs/{job_id}/control: transitions, revisions, replay and policy_patch."""

from __future__ import annotations

from contract_server.tests import builders
from contract_server.tests.client import Client
from contract_server.tests.conftest import FakeClock
from contract_server.tests.flow import Flow
from contract_server.util import Json


def control(
    client: Client, job_id: str, action: str, revision: int, key: str | None = None, **extra: Json
) -> tuple[int, Json]:
    body: Json = {
        "client_request_id": key or f"{action}-{revision}",
        "action": action,
        "expected_state_revision": revision,
    }
    body.update(extra)
    return client.system_post(f"/jobs/{job_id}/control", body)


def test_pause_and_resume_with_a_live_lease(flow: Flow, client: Client) -> None:
    job = flow.start()
    status, body = control(client, job.job_id, "pause", 0)
    assert status == 200
    assert (body["state"], body["state_revision"]) == ("paused", 1)
    assert body["command_id"]
    status, body = control(client, job.job_id, "resume", 1)
    assert (body["state"], body["state_revision"]) == ("leased", 2)


def test_resume_after_lease_expiry_requeues(flow: Flow, client: Client, clock: FakeClock) -> None:
    job = flow.start()
    control(client, job.job_id, "pause", 0)
    clock.advance(400)
    assert flow.job_status(job.job_id)["state"] == "paused"
    assert control(client, job.job_id, "resume", 1)[1]["state"] == "queued"
    item = flow.claim()[0]
    assert item["lease"]["run_id"] == job.lease["run_id"]


def test_revision_conflict_is_409(flow: Flow, client: Client) -> None:
    job = flow.start()
    status, body = control(client, job.job_id, "pause", 5)
    assert (status, body["code"]) == (409, "invalid_input")
    assert body["detail"] == "state revision is 0"


def test_replay_returns_the_same_response(flow: Flow, client: Client) -> None:
    job = flow.start()
    first = control(client, job.job_id, "pause", 0, key="k1")
    second = control(client, job.job_id, "pause", 0, key="k1")
    assert first == second
    assert flow.job_status(job.job_id)["state_revision"] == 1
    status, body = control(client, job.job_id, "cancel", 1, key="k1")
    assert (status, body["code"]) == (409, "idempotency_conflict")


def test_invalid_transitions_are_409(flow: Flow, client: Client) -> None:
    job = flow.start()
    for action in ("resume", "continue"):
        status, body = control(client, job.job_id, action, 0)
        assert (status, body["code"]) == (409, "invalid_input"), action
    assert control(client, job.job_id, "cancel", 0)[1]["state"] == "cancelled"
    for action in ("pause", "cancel", "continue"):
        status, body = control(client, job.job_id, action, 1)
        assert (status, body["code"]) == (409, "invalid_input"), action


def test_continue_merges_policy_patch_and_starts_a_new_run(flow: Flow, client: Client) -> None:
    job = flow.start()
    flow.finish(job, "partial")
    patch = {"campaign_max_pages": 1200, "max_runs": 9}
    status, body = control(client, job.job_id, "continue", 0, policy_patch=patch)
    assert (status, body["state"]) == (200, "queued")
    item = flow.claim()[0]
    assert item["lease"]["run_id"] != job.lease["run_id"]
    assert item["job"]["policy"]["campaign_max_pages"] == 1200
    assert item["job"]["policy"]["max_runs"] == 9
    assert item["checkpoint"]["pages_consumed"] == 3


def test_invalid_policy_patch_is_400(flow: Flow, client: Client) -> None:
    job = flow.start()
    status, body = control(client, job.job_id, "pause", 0, policy_patch={"max_pages": 0})
    assert (status, body["code"]) == (400, "invalid_input")


def test_control_of_an_unclaimed_job_queues_no_command(flow: Flow, client: Client) -> None:
    created = flow.batch(builders.company("c1"))
    job_id = created["jobs"][0]["job_id"]
    assert control(client, job_id, "pause", 0)[1]["state"] == "paused"
    status, beat = client.post("/workers/heartbeat", builders.heartbeat_body())
    assert (status, beat["commands"]) == (200, [])
    status, body = control(client, "missing", "pause", 0)
    assert (status, body["code"]) == (404, "invalid_input")
