"""Heartbeat lease renewal (renewed/expired/mismatch/cancelled), commands and acks."""

from __future__ import annotations

from contract_server.tests import builders
from contract_server.tests.client import WORKER2_ID, WORKER2_TOKEN, Client
from contract_server.tests.conftest import FakeClock
from contract_server.tests.flow import Flow, Job
from contract_server.util import Json

HEARTBEAT = "/workers/heartbeat"


def beat(client: Client, *leases: Json, acks: list[Json] | None = None) -> Json:
    status, body = client.post(HEARTBEAT, builders.heartbeat_body(list(leases), acks))
    assert status == 200, body
    return body


def control(client: Client, job_id: str, action: str, revision: int) -> Json:
    body = {
        "client_request_id": f"{action}-{revision}",
        "action": action,
        "expected_state_revision": revision,
    }
    status, payload = client.system_post(f"/jobs/{job_id}/control", body)
    assert status == 200, payload
    return payload


def test_current_lease_is_renewed(client: Client, flow: Flow, clock: FakeClock) -> None:
    job = flow.start()
    clock.advance(170)
    body = beat(client, builders.active_lease(job.lease))
    renewal = body["leases"][0]
    assert renewal["status"] == "renewed"
    assert renewal["lease_expires_at"].startswith("2026-10-04T12:05:50")
    clock.advance(170)
    assert flow.job_status(job.job_id)["state"] == "leased"


def test_expired_lease_is_not_renewed(client: Client, flow: Flow, clock: FakeClock) -> None:
    job = flow.start()
    clock.advance(181)
    renewal = beat(client, builders.active_lease(job.lease))["leases"][0]
    assert (renewal["status"], renewal["lease_expires_at"]) == ("expired", None)


def test_stale_generation_or_token_is_a_mismatch(client: Client, flow: Flow) -> None:
    job = flow.start()
    stale = dict(builders.active_lease(job.lease), lease_generation=7)
    wrong = dict(builders.active_lease(job.lease), execution_token="forged")
    unknown = dict(builders.active_lease(job.lease), job_id="nope")
    body = beat(client, stale, wrong, unknown)
    assert [item["status"] for item in body["leases"]] == ["mismatch"] * 3


def test_other_workers_lease_is_a_mismatch(client: Client, flow: Flow) -> None:
    job = flow.start()
    body = builders.heartbeat_body([builders.active_lease(job.lease)], worker_id=WORKER2_ID)
    status, payload = client.post(HEARTBEAT, body, token=WORKER2_TOKEN)
    assert status == 200
    assert payload["leases"][0]["status"] == "mismatch"


def test_cancelled_job_lease_reports_cancelled(client: Client, flow: Flow) -> None:
    job = flow.start()
    control(client, job.job_id, "cancel", 0)
    renewal = beat(client, builders.active_lease(job.lease))["leases"][0]
    assert renewal["status"] == "cancelled"


def test_commands_arrive_until_acknowledged(client: Client, flow: Flow) -> None:
    job = flow.start()
    pause = control(client, job.job_id, "pause", 0)
    resume = control(client, job.job_id, "resume", 1)
    commands = beat(client)["commands"]
    assert [c["command_id"] for c in commands] == [pause["command_id"], resume["command_id"]]
    assert [c["action"] for c in commands] == ["pause", "resume"]
    assert [c["state_revision"] for c in commands] == [1, 2]
    ack = {"command_id": pause["command_id"], "status": "applied", "detail": ""}
    commands = beat(client, acks=[ack])["commands"]
    assert [c["command_id"] for c in commands] == [resume["command_id"]]


def test_commands_only_reach_the_pinned_worker(client: Client, flow: Flow) -> None:
    job = flow.start()
    control(client, job.job_id, "pause", 0)
    other = builders.heartbeat_body(worker_id=WORKER2_ID)
    status, payload = client.post(HEARTBEAT, other, token=WORKER2_TOKEN)
    assert (status, payload["commands"]) == (200, [])


def test_paused_job_keeps_its_lease_through_heartbeats(
    client: Client, flow: Flow, clock: FakeClock
) -> None:
    job = flow.start()
    control(client, job.job_id, "pause", 0)
    clock.advance(170)
    assert beat(client, builders.active_lease(job.lease))["leases"][0]["status"] == "renewed"
    clock.advance(170)
    assert control(client, job.job_id, "resume", 1)["state"] == "leased"


def test_heartbeat_feeds_worker_status(client: Client, flow: Flow) -> None:
    job: Job = flow.start()
    status, _ = client.post(
        HEARTBEAT,
        builders.heartbeat_body([builders.active_lease(job.lease)], outbox_pending=3),
    )
    assert status == 200
    status, worker = client.get("/workers/worker-main-pc/status")
    assert status == 200
    assert worker["connected"] is True
    assert worker["active_job_ids"] == [job.job_id]
    assert (worker["outbox_pending"], worker["transport_state"]) == (3, "syncing")
