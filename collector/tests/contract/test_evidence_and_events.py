"""Evidence before observation, seq, idempotency, K7, FieldAudit, job.finished."""

from __future__ import annotations

import pytest
from argus_collector.api_client import contract as api

from collector.tests.contract.conftest import Argus
from collector.tests.contract.system import company
from collector.tests.contract.worker import (
    claim,
    phone_contact,
    post,
    post_raw,
    started,
    upload,
    without_audit,
)


@pytest.fixture
def job(argus: Argus) -> api.ClaimedJob:
    argus.system.batch([company()])
    return claim(argus)[0]


def test_observation_before_its_snapshot_waits_for_it(argus: Argus, job: api.ClaimedJob) -> None:
    """Contract 3.1.0 (ARGUS 0.4.24.4): accepted + evidence_pending, the upload applies it."""
    contact = phone_contact(job, 1, "not-uploaded-yet")
    resp = post(argus, job, [contact])
    first = resp.results[0]
    assert (first.status.value, first.code) == ("accepted", "evidence_pending")
    assert resp.last_contiguous_seq == 1 and not first.state_applied
    assert post(argus, job, [contact]).results[0].code == "evidence_pending", "still waits"
    evidence = upload(argus, job, evidence_id="not-uploaded-yet")
    assert evidence.status.value == "accepted"
    again = post(argus, job, [contact]).results[0]
    assert (again.status.value, again.code) == ("duplicate", None)
    assert again.channel_status == api.ChannelStatus("published_direct")


def test_evidence_upload_is_idempotent(argus: Argus, job: api.ClaimedJob) -> None:
    first = upload(argus, job)
    assert first.status.value == "accepted" and first.snapshot_id
    again = upload(argus, job, evidence_id=first.evidence_id)
    assert again.status.value == "duplicate" and again.sha256 == first.sha256


def test_sequence_gap_rejects_the_tail(argus: Argus, job: api.ClaimedJob) -> None:
    resp = post(argus, job, [started(job, 2), started(job, 3)])
    assert [r.code for r in resp.results] == ["sequence_gap", "sequence_gap"]
    assert resp.last_contiguous_seq == 0


def test_changed_payload_under_an_accepted_id_conflicts(argus: Argus, job: api.ClaimedJob) -> None:
    event = started(job, 1)
    assert post(argus, job, [event]).results[0].status.value == "accepted"
    changed = api.JobStartedEvent(event_id=event.event_id, job_id=event.job_id,
                                  run_id=event.run_id, seq=1, occurred_at=event.occurred_at,
                                  payload=api.StartedPayload(stage=api.Stage("http"),
                                                             worker_version="other"))
    with pytest.raises(api.ApiError) as err:
        post(argus, job, [changed])
    assert err.value.status == 409 and err.value.error is not None
    assert err.value.error.code == "idempotency_conflict"


def test_channel_from_a_host_outside_approved_hosts(argus: Argus, job: api.ClaimedJob) -> None:
    evidence = upload(argus, job, final_url="https://katsa-group.example/")
    result = post(argus, job, [phone_contact(job, 1, evidence.evidence_id)]).results[0]
    assert (result.status.value, result.code) == ("rejected", "host_not_approved")


def test_contact_without_field_audit_is_rejected(argus: Argus, job: api.ClaimedJob) -> None:
    evidence = upload(argus, job)
    body = {"schema_version": "1.1", "execution_token": job.lease.execution_token,
            "events": [without_audit(phone_contact(job, 1, evidence.evidence_id))]}
    status, data = post_raw(argus, job.job.job_id, body)
    assert status == 200 and data["results"][0]["code"] == "field_audit_missing"


def test_wrong_token_is_a_lease_mismatch(argus: Argus, job: api.ClaimedJob) -> None:
    with pytest.raises(api.ApiError) as err:
        post(argus, job, [started(job, 1)], token="not-the-lease")
    assert err.value.status == 409 and err.value.error is not None
    assert err.value.error.code == "lease_mismatch"


def test_finished_needs_every_earlier_seq(argus: Argus, job: api.ClaimedJob) -> None:
    from collector.tests.contract.finished import finished  # noqa: PLC0415

    assert post(argus, job, [started(job, 1)]).results[0].status.value == "accepted"
    wrong = post(argus, job, [finished(job, 2, last_content_seq=0)])
    assert wrong.results[0].code == "sequence_gap" and wrong.job_state.value != "completed"
    right = post(argus, job, [finished(job, 2, last_content_seq=1)])
    assert right.results[0].status.value == "accepted"
    assert right.job_state.value == "completed" and not right.next_run_scheduled
    assert argus.system.job(job.job.job_id)["coverage"]["confirmation"] == "unverified"
