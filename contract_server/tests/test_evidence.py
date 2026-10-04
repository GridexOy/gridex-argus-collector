"""POST /jobs/{job_id}/evidence: ownership, tokens, idempotency, hashes, sizes, text."""

from __future__ import annotations

from contract_server.tests import builders
from contract_server.tests.client import Client
from contract_server.tests.flow import Flow
from contract_server.util import sha256_hex

MIB = 1024 * 1024


def test_upload_is_accepted_with_a_snapshot(flow: Flow) -> None:
    job = flow.start()
    status, body = flow.upload(job, b"<p>hello</p>", evidence_id="ev-1")
    assert status == 201
    assert (body["evidence_id"], body["status"]) == ("ev-1", "accepted")
    assert body["sha256"] == sha256_hex(b"<p>hello</p>")
    assert body["snapshot_id"]


def test_replay_is_duplicate_and_other_content_conflicts(flow: Flow) -> None:
    job = flow.start()
    _, first = flow.upload(job, b"<p>one</p>", evidence_id="ev-1")
    status, again = flow.upload(job, b"<p>one</p>", evidence_id="ev-1")
    assert (status, again["status"], again["snapshot_id"]) == (
        200,
        "duplicate",
        first["snapshot_id"],
    )
    status, body = flow.upload(job, b"<p>two</p>", evidence_id="ev-1")
    assert (status, body["code"]) == (409, "idempotency_conflict")


def test_hash_or_length_mismatch_is_422(flow: Flow) -> None:
    job = flow.start()
    status, body = flow.upload(job, b"<p>x</p>", sha256="a" * 64)
    assert (status, body["code"]) == (422, "evidence_hash_mismatch")
    status, body = flow.upload(job, b"<p>x</p>", byte_length=3)
    assert (status, body["code"]) == (422, "evidence_hash_mismatch")
    status, body = flow.upload(job, b"<p>x</p>", canonical_text="x", canonical_text_sha256="b" * 64)
    assert (status, body["code"]) == (422, "evidence_hash_mismatch")


def test_size_limits_by_source_kind(flow: Flow) -> None:
    job = flow.start()
    big = b"\x89PNG" + b"\0" * (10 * MIB)
    status, body = flow.upload(job, big, source_kind="screenshot", mime_type="image/png")
    assert (status, body["code"]) == (413, "payload_too_large")
    status, body = flow.upload(job, big, source_kind="document", mime_type="application/pdf")
    assert status == 201, body
    status, body = flow.upload(job, b"<p/>", byte_length=26 * MIB)
    assert (status, body["code"]) == (413, "payload_too_large")


def test_ownership_is_checked(flow: Flow) -> None:
    job = flow.start()
    for field, value in (("job_id", "other"), ("company_id", "c9"), ("run_id", "r9")):
        status, body = flow.upload(job, b"<p/>", **{field: value})
        assert (status, body["code"]) == (400, "invalid_input"), field


def test_execution_token_is_required_and_checked(flow: Flow, client: Client) -> None:
    job = flow.start()
    data = b"<p/>"
    meta = builders.metadata(job.lease, job.company_id, data, "ev-1")
    status, body = client.upload(job.job_id, meta, data, None)
    assert (status, body["code"]) == (400, "invalid_input")
    status, body = client.upload(job.job_id, meta, data, "forged")
    assert (status, body["code"]) == (409, "lease_mismatch")


def test_metadata_is_validated_against_the_contract(flow: Flow) -> None:
    job = flow.start()
    status, body = flow.upload(job, b"<p/>", source_kind="video")
    assert (status, body["code"]) == (400, "invalid_input")
    assert "source_kind" in body["detail"]


def test_malformed_multipart_is_invalid_input(flow: Flow, client: Client) -> None:
    job = flow.start()
    headers = {"Content-Type": "multipart/form-data; boundary=zz", "X-Execution-Token": job.token}
    status, body = client.request(
        "POST", f"/jobs/{job.job_id}/evidence", b"garbage", headers=headers
    )
    assert (status, body["code"]) == (400, "invalid_input")


def test_unknown_job_is_404(flow: Flow, client: Client) -> None:
    job = flow.start()
    meta = builders.metadata(job.lease, job.company_id, b"x", "ev-1")
    status, body = client.upload("missing", meta, b"x", job.token)
    assert (status, body["code"]) == (404, "invalid_input")


def test_checkpoint_is_not_a_snapshot(flow: Flow) -> None:
    job = flow.start()
    status, body = flow.upload(
        job, b'{"frontier": []}', source_kind="checkpoint", mime_type="application/json"
    )
    assert (status, body["snapshot_id"]) == (201, None)


def test_text_is_derived_from_html_or_taken_from_canonical_text(flow: Flow, client: Client) -> None:
    job = flow.start()
    derived = flow.page(job, evidence_id="ev-html")
    _, view = client.get(f"/_stand/evidence/{derived}")
    assert "Anna Virtanen Sales Manager +358 40 123 4567" in view["text"]
    assert "var phone" not in view["text"] and "color" not in view["text"]
    assert "& info@example.fi" in view["text"]
    assert view["metadata"]["evidence_id"] == "ev-html"
    text = "Canonical text"
    status, _ = flow.upload(
        job,
        b"<p/>",
        evidence_id="ev-canon",
        canonical_text=text,
        canonical_text_sha256=sha256_hex(text.encode()),
    )
    assert status == 201
    assert client.get("/_stand/evidence/ev-canon")[1]["text"] == text
