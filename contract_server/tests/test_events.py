"""POST /jobs/{job_id}/events: envelope, ordering, idempotency and per-event rejections."""

from __future__ import annotations

from contract_server.tests import builders, payloads
from contract_server.tests.client import WORKER2_TOKEN, Client
from contract_server.tests.flow import Flow, Job
from contract_server.util import Json

PHONE = "+358 40 123 4567"


def phone_event(flow: Flow, job: Job, evidence_id: str) -> Json:
    return flow.contact(job, evidence_id, [payloads.observation("phone", PHONE, evidence_id)])


def statuses(body: Json) -> list[tuple[str, str | None]]:
    return [(result["status"], result["code"]) for result in body["results"]]


def test_accepted_events_advance_the_sequence(flow: Flow) -> None:
    job = flow.start()
    evidence_id = flow.page(job)
    status, body = flow.send(
        job,
        flow.event(job, "job.started", payloads.started()),
        flow.event(job, "source.processed", payloads.source([evidence_id])),
        phone_event(flow, job, evidence_id),
        flow.event(job, "model.called", payloads.model_called()),
    )
    assert status == 200
    assert statuses(body) == [("accepted", None)] * 4
    assert body["last_contiguous_seq"] == 4
    assert (body["job_state"], body["next_run_scheduled"]) == ("running", False)
    assert all(result["state_applied"] for result in body["results"])
    revisions = [result["server_revision"] for result in body["results"]]
    assert revisions == sorted(revisions) and len(set(revisions)) == 4
    assert body["results"][2]["canonical_contact_id"]


def test_replay_is_duplicate_and_changed_payload_is_409(flow: Flow) -> None:
    job = flow.start()
    evidence_id = flow.page(job)
    contact = phone_event(flow, job, evidence_id)
    _, first = flow.send(job, contact)
    status, again = flow.send(job, contact)
    assert status == 200
    assert statuses(again) == [("duplicate", None)]
    assert (
        again["results"][0]["canonical_contact_id"] == first["results"][0]["canonical_contact_id"]
    )
    assert again["results"][0]["channel_status"] == "published_direct"
    changed = dict(contact, occurred_at="2026-10-04T12:30:00Z")
    status, body = flow.send(job, flow.event(job, "job.progress", payloads.progress()), changed)
    assert (status, body["code"]) == (409, "idempotency_conflict")
    status, body = flow.send(job, flow.event(job, "job.progress", payloads.progress()))
    assert (body["results"][0]["seq"], body["last_contiguous_seq"]) == (3, 1), "409 applied"
    assert statuses(body) == [("rejected", "sequence_gap")]


def test_gap_rejects_the_whole_tail(flow: Flow) -> None:
    job = flow.start()
    job.seq = 1
    body = flow.send(
        job,
        flow.event(job, "job.started", payloads.started()),
        builders.event(job.lease, 1, "job.progress", payloads.progress()),
    )[1]
    assert statuses(body) == [("rejected", "sequence_gap")] * 2
    assert body["last_contiguous_seq"] == 0


def test_evidence_missing_does_not_advance_and_retry_works(flow: Flow) -> None:
    job = flow.start()
    contact = phone_event(flow, job, "ev-later")
    progress = flow.event(job, "job.progress", payloads.progress())
    body = flow.send(job, contact, progress)[1]
    assert statuses(body) == [("rejected", "evidence_missing"), ("rejected", "sequence_gap")]
    assert body["last_contiguous_seq"] == 0
    flow.page(job, evidence_id="ev-later")
    body = flow.send(job, contact, progress)[1]
    assert statuses(body) == [("accepted", None)] * 2
    assert body["last_contiguous_seq"] == 2


def test_schema_errors_are_recorded_rejections(flow: Flow, client: Client) -> None:
    job = flow.start()
    evidence_id = flow.page(job)
    no_audit = phone_event(flow, job, evidence_id)
    del no_audit["payload"]["field_audit"]
    bad_stage = flow.event(job, "job.started", {"stage": "teleport", "worker_version": "1"})
    unknown = flow.event(job, "job.exploded", {})
    body = flow.send(job, no_audit, bad_stage, unknown)[1]
    assert statuses(body) == [
        ("rejected", "field_audit_missing"),
        ("rejected", "invalid_input"),
        ("rejected", "invalid_input"),
    ]
    assert body["last_contiguous_seq"] == 3
    assert not any(result["state_applied"] for result in body["results"])
    rejected = client.get(f"/_stand/jobs/{job.job_id}/contacts")[1]["rejected"]
    assert [row["code"] for row in rejected] == [
        "field_audit_missing",
        "invalid_input",
        "invalid_input",
    ]


def test_envelope_errors_are_400(flow: Flow, client: Client) -> None:
    job = flow.start()
    started = flow.event(job, "job.started", payloads.started())
    path = f"/jobs/{job.job_id}/events"
    old = dict(builders.events_body(job.token, [started]), schema_version="1.0")
    assert client.post(path, old)[1]["code"] == "schema_unsupported"
    cases: list[Json] = [
        builders.events_body(job.token, []),
        builders.events_body(job.token, [started] * 51),
        builders.events_body(job.token, [dict(started, job_id="other")]),
        builders.events_body(job.token, [started, dict(started, run_id="r2", event_id="x")]),
        builders.events_body(job.token, [dict(started, run_id="not-a-run")]),
    ]
    for body in cases:
        status, payload = client.post(path, body)
        assert (status, payload["code"]) == (400, "invalid_input"), payload


def test_unknown_token_is_lease_mismatch(flow: Flow) -> None:
    job = flow.start()
    status, body = flow.send(job, flow.event(job, "job.started", payloads.started()), token="x")
    assert (status, body["code"]) == (409, "lease_mismatch")


def test_model_calls_and_sources_are_stored(flow: Flow, client: Client) -> None:
    job = flow.start()
    evidence_id = flow.page(job)
    flow.send(
        job,
        flow.event(job, "model.called", payloads.model_called()),
        flow.event(job, "source.processed", payloads.source([evidence_id])),
        flow.event(job, "source.discovered", payloads.source()),
    )
    view = client.get(f"/_stand/jobs/{job.job_id}/contacts")[1]
    call = view["model_calls"][0]
    assert (call["provider"], call["model_id"], call["cost_eur"]) == ("local", "qwen-test", 0)
    assert (call["input_tokens"], call["run_id"]) == (900, job.lease["run_id"])
    assert [source["type"] for source in view["sources"]] == [
        "source.processed",
        "source.discovered",
    ]
    assert flow.job_status(job.job_id)["counts"]["pages_processed"] == 1


def test_other_worker_cannot_deliver_with_a_leaked_token(flow: Flow, client: Client) -> None:
    job = flow.start()
    body = builders.events_body(job.token, [flow.event(job, "job.started", payloads.started())])
    status, payload = client.post(f"/jobs/{job.job_id}/events", body, token=WORKER2_TOKEN)
    assert (status, payload["code"]) == (409, "lease_mismatch")
