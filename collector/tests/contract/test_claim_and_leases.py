"""Claim, leases, heartbeat, commands, reconcile — through the generated client."""

from __future__ import annotations

from argus_collector.api_client import contract as api

from collector.tests.contract.conftest import Argus
from collector.tests.contract.system import company
from collector.tests.contract.worker import CAPS, claim


def test_claim_is_at_most_max_jobs_and_never_twice(argus: Argus) -> None:
    status, _ = argus.system.batch([company() for _ in range(3)])
    assert status == 201
    first = claim(argus, max_jobs=2)
    second = claim(argus, max_jobs=8)
    assert len(first) == 2 and len(second) == 1
    assert not {j.job.job_id for j in first} & {j.job.job_id for j in second}
    assert claim(argus) == [], "an empty queue is an empty list"
    lease = first[0].lease
    assert lease.lease_generation == 1 and lease.execution_token and first[0].checkpoint is None
    assert first[0].job.schema_version == "1.1" and first[0].routes == []


def test_participation_must_be_confirmed(argus: Argus) -> None:
    bad = company(participation_status="owner_override", participation_claim_id=None)
    status, data = argus.system.batch([bad])
    assert status == 422 and data["code"] == "participation_not_confirmed"


def heartbeat(argus: Argus, leases: list[api.ActiveLease],
              acks: list[api.CommandAck]) -> api.HeartbeatResponse:
    request = api.HeartbeatRequest(
        worker_id=argus.worker_id, worker_version="contract-tests", schema_versions=["1.1"],
        capabilities=CAPS, collecting=True, active_jobs=leases, outbox_pending=0,
        free_job_slots=7, browser_available=True, model_available=True, acknowledgements=acks,
    )
    mode: api.ProxyMode = "direct" if argus.proxy == "direct" else "system"
    return api.heartbeat(argus.base_url, argus.token, request, proxy_mode=mode)


def test_heartbeat_renews_and_delivers_commands_until_acked(argus: Argus) -> None:
    argus.system.batch([company()])
    job = claim(argus)[0]
    active = [api.ActiveLease(job_id=job.job.job_id, run_id=job.lease.run_id,
                              execution_token=job.lease.execution_token,
                              lease_generation=job.lease.lease_generation)]
    assert heartbeat(argus, active, []).leases[0].status.value == "renewed"
    control = argus.system.control(job.job.job_id, "pause")
    commands = heartbeat(argus, active, []).commands
    assert [(c.command_id, c.action.value) for c in commands] == [(control["command_id"], "pause")]
    ack = api.CommandAck(command_id=control["command_id"],
                         status=api.CommandAckStatus("applied"), detail="")
    assert heartbeat(argus, active, [ack]).commands == []


def test_cancelled_job_reconciles_to_drain_only(argus: Argus) -> None:
    argus.system.batch([company()])
    job = claim(argus)[0]
    argus.system.control(job.job.job_id, "cancel")
    request = api.ReconcileRequest(worker_id=argus.worker_id, run_id=job.lease.run_id,
                                   last_acknowledged_seq=0, pending_event_ids=[],
                                   pending_evidence_ids=["never-uploaded"])
    mode: api.ProxyMode = "direct" if argus.proxy == "direct" else "system"
    resp = api.reconcile_job(argus.base_url, argus.token, job.job.job_id, request,
                             proxy_mode=mode)
    assert resp.mode.value == "drain_only" and resp.job_state.value == "cancelled"
    assert resp.missing_evidence_ids == ["never-uploaded"]
    assert resp.lease.run_id == job.lease.run_id
