"""POST /batches: creation, idempotency, R8 participation and rerun_reason."""

from __future__ import annotations

from contract_server.tests import builders
from contract_server.tests.client import Client


def test_batch_creates_one_queued_job_per_company(client: Client) -> None:
    body = builders.batch_body(builders.company("c1"), builders.company("c2"))
    status, created = client.system_post("/batches", body)
    assert status == 201
    assert [job["company_id"] for job in created["jobs"]] == ["c1", "c2"]
    status, batch = client.get(f"/batches/{created['batch_id']}")
    assert status == 200
    assert [job["state"] for job in batch["jobs"]] == ["queued", "queued"]
    assert all(job["state_revision"] == 0 for job in batch["jobs"])
    assert all(job["current_run_id"] is None for job in batch["jobs"])


def test_replay_returns_200_with_the_same_response(client: Client) -> None:
    body = builders.batch_body(builders.company("c1"))
    first = client.system_post("/batches", body)
    second = client.system_post("/batches", body)
    assert first[0] == 201
    assert second == (200, first[1])


def test_same_key_with_another_payload_is_a_conflict(client: Client) -> None:
    body = builders.batch_body(builders.company("c1"), client_request_id="key-1")
    client.system_post("/batches", body)
    other = builders.batch_body(builders.company("c2"), client_request_id="key-1")
    status, payload = client.system_post("/batches", other)
    assert (status, payload["code"]) == (409, "idempotency_conflict")


def test_confirmed_without_claim_id_is_not_confirmed(client: Client) -> None:
    body = builders.batch_body(builders.company("c1", participation_claim_id=None))
    status, payload = client.system_post("/batches", body)
    assert (status, payload["code"]) == (422, "participation_not_confirmed")
    assert "c1" in payload["detail"]


def test_strong_historical_needs_a_claim_id(client: Client) -> None:
    company = builders.company(
        "c1", participation_status="strong_historical", participation_claim_id=" "
    )
    status, payload = client.system_post("/batches", builders.batch_body(company))
    assert (status, payload["code"]) == (422, "participation_not_confirmed")


def test_owner_override_needs_a_reason(client: Client) -> None:
    company = builders.company(
        "c1", participation_status="owner_override", participation_claim_id=None
    )
    status, payload = client.system_post("/batches", builders.batch_body(company))
    assert (status, payload["code"]) == (422, "participation_not_confirmed")
    company["override_reason"] = "owner asked"
    status, _ = client.system_post("/batches", builders.batch_body(company))
    assert status == 201


def test_unknown_participation_status_is_invalid_input(client: Client) -> None:
    company = builders.company("c1", participation_status="maybe")
    status, payload = client.system_post("/batches", builders.batch_body(company))
    assert (status, payload["code"]) == (400, "invalid_input")


def test_rerun_needs_rerun_reason(client: Client) -> None:
    client.system_post("/batches", builders.batch_body(builders.company("c1")))
    status, payload = client.system_post("/batches", builders.batch_body(builders.company("c1")))
    assert (status, payload["code"]) == (422, "invalid_input")
    assert "rerun_reason" in payload["detail"]
    rerun = builders.company("c1", rerun_reason="freshness check")
    status, _ = client.system_post("/batches", builders.batch_body(rerun))
    assert status == 201


def test_same_company_in_another_project_is_not_a_rerun(client: Client) -> None:
    client.system_post("/batches", builders.batch_body(builders.company("c1")))
    other = builders.company("c1", project_id="p2")
    status, _ = client.system_post("/batches", builders.batch_body(other))
    assert status == 201


def test_batch_limits_come_from_the_schema(client: Client) -> None:
    companies = [builders.company(f"c{i}") for i in range(9)]
    status, payload = client.system_post("/batches", builders.batch_body(*companies))
    assert (status, payload["code"]) == (400, "invalid_input")
    assert "at most 8" in payload["detail"]
    bad_url = builders.company("c1", seed_urls=["not a url"])
    status, payload = client.system_post("/batches", builders.batch_body(bad_url))
    assert (status, payload["code"]) == (400, "invalid_input")
    assert "seed_urls[0]" in payload["detail"]


def test_failed_batch_creates_nothing(client: Client) -> None:
    good, bad = builders.company("c1"), builders.company("c2", participation_claim_id=None)
    status, _ = client.system_post("/batches", builders.batch_body(good, bad))
    assert status == 422
    status, _ = client.system_post("/batches", builders.batch_body(builders.company("c1")))
    assert status == 201
