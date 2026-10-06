"""Contact events: quote checks, K7 hosts, K3 channel status, canonical contacts."""

from __future__ import annotations

import pytest

from contract_server.channels import channel_status
from contract_server.tests import builders, payloads
from contract_server.tests.client import Client
from contract_server.tests.flow import Flow
from contract_server.util import Json, sha256_hex

PHONE = "+358 40 123 4567"
EMAIL = "anna.virtanen@example.fi"
NAME = "Anna Virtanen"


def send_one(flow: Flow, observations: list[Json], evidence_id: str, **kw: str) -> Json:
    job = flow.start(company_id=f"c-{evidence_id}")
    flow.page(job, evidence_id=evidence_id)
    body = flow.send(job, flow.contact(job, evidence_id, observations, **kw))[1]
    result: Json = body["results"][0]
    return result


@pytest.mark.parametrize(
    ("entity_type", "binding", "extraction", "expected"),
    [
        ("person", "card", "confirmed", "published_direct"),
        ("person", "table_row", "confirmed", "published_direct"),
        ("person", "proximity_only", "confirmed", "inferred"),
        ("person", "none", "confirmed", "inferred"),
        ("person", "card", "ambiguous", "inferred"),
        ("person", "card", "ocr_unverified", "inferred"),
        ("organization_channel", "caption", "confirmed", "published_general"),
        ("office", "card", "confirmed", "published_general"),
        ("department", "none", "confirmed", "inferred"),
        ("unassigned_channel", "card", "confirmed", "inferred"),
        ("person", "card", "historical", "stale"),
        ("organization_channel", "caption", "historical", "stale"),
    ],
)
def test_channel_status_table(
    entity_type: str, binding: str, extraction: str, expected: str
) -> None:
    obs = payloads.observation("phone", PHONE, "ev", binding=binding, status=extraction)
    assert channel_status(entity_type, obs) == expected


def test_non_channel_fields_have_no_status() -> None:
    for field in ("email_pattern", "full_name", "title"):
        assert channel_status("person", payloads.observation(field, "x", "ev")) is None
    assert channel_status("person", payloads.observation("phone_direct", PHONE, "ev")) is not None


@pytest.mark.parametrize(
    ("entity_type", "binding", "expected"),
    [
        ("person", "card", "published_direct"),
        ("person", "proximity_only", "inferred"),
        ("organization_channel", "caption", "published_general"),
        ("unassigned_channel", "none", "inferred"),
    ],
)
def test_channel_status_over_http(
    flow: Flow, entity_type: str, binding: str, expected: str
) -> None:
    obs = payloads.observation("phone", PHONE, "ev-1", binding=binding)
    result = send_one(flow, [obs], "ev-1", entity_type=entity_type)
    assert (result["status"], result["channel_status"]) == ("accepted", expected)


def test_event_status_is_the_strongest_channel(flow: Flow) -> None:
    observations = [
        payloads.observation("full_name", "Anna Virtanen", "ev-1"),
        payloads.observation("email", EMAIL, "ev-1", binding="proximity_only"),
        payloads.observation("phone", PHONE, "ev-1"),
    ]
    assert send_one(flow, observations, "ev-1")["channel_status"] == "published_direct"
    name_only = [payloads.observation("full_name", "Anna Virtanen", "ev-2")]
    assert send_one(flow, name_only, "ev-2", entity_id="e2")["channel_status"] is None


def test_quote_not_in_evidence_is_hash_mismatch(flow: Flow) -> None:
    obs = payloads.observation("phone", "+358 40 999 9999", "ev-1")
    result = send_one(flow, [obs], "ev-1")
    assert (result["status"], result["code"]) == ("rejected", "evidence_hash_mismatch")
    blank = payloads.observation("phone", PHONE, "ev-2", quote="  ")
    assert send_one(flow, [blank], "ev-2")["code"] == "evidence_hash_mismatch"


def test_quote_search_ignores_whitespace_and_reads_raw_bytes(flow: Flow) -> None:
    spaced = payloads.observation("phone", PHONE, "ev-1", quote="+358  40\n123 4567")
    assert send_one(flow, [spaced], "ev-1")["status"] == "accepted"
    raw_only = payloads.observation("email", "info@example.fi", "ev-2", quote="&amp; info@")
    assert send_one(flow, [raw_only], "ev-2", entity_id="e2")["status"] == "accepted"


def test_text_span_with_matching_hash_must_be_exact(flow: Flow, client: Client) -> None:
    job = flow.start()
    evidence_id = flow.page(job, evidence_id="ev-1")
    text = client.get(f"/_stand/evidence/{evidence_id}")[1]["text"]
    start = text.index(PHONE)
    span = {
        "kind": "text_span",
        "start": start,
        "end": start + len(PHONE),
        "text_sha256": sha256_hex(text.encode("utf-8")),
    }
    good = payloads.observation("phone", PHONE, evidence_id, locator=span)
    shifted = payloads.observation("phone", PHONE, evidence_id, locator=dict(span, start=start + 1))
    body = flow.send(
        job, flow.contact(job, evidence_id, [good]), flow.contact(job, evidence_id, [shifted])
    )[1]
    assert [r["status"] for r in body["results"]] == ["accepted", "rejected"]
    assert body["results"][1]["code"] == "evidence_hash_mismatch"
    stale_hash = dict(span, start=0, end=3, text_sha256="f" * 64)
    hinted = payloads.observation("phone", PHONE, evidence_id, locator=stale_hash)
    assert (
        flow.send(job, flow.contact(job, evidence_id, [hinted]))[1]["results"][0]["status"]
        == "accepted"
    )


def test_channel_from_unapproved_host_is_rejected(flow: Flow) -> None:
    job = flow.start()
    other = flow.page(job, evidence_id="ev-x", final_url="https://example.fi.evil.test/contact")
    sub = flow.page(job, evidence_id="ev-s", final_url="https://shop.example.fi/contact")
    approved = flow.page(job, evidence_id="ev-ok", final_url="https://WWW.Example.FI/c")
    events = [
        flow.contact(job, other, [payloads.observation("phone", PHONE, other)]),
        flow.contact(job, sub, [payloads.observation("email", EMAIL, sub)]),
        flow.contact(job, other, [payloads.observation("title", "Sales Manager", other)]),
        flow.contact(job, approved, [payloads.observation("phone", PHONE, approved)]),
    ]
    body = flow.send(job, *events)[1]
    assert [(r["status"], r["code"]) for r in body["results"]] == [
        ("rejected", "host_not_approved"),
        ("rejected", "host_not_approved"),
        ("accepted", None),
        ("accepted", None),
    ]
    assert body["last_contiguous_seq"] == 4


def test_canonical_contact_is_stable_and_observations_deduplicate(
    flow: Flow, client: Client
) -> None:
    job = flow.start()
    evidence_id = flow.page(job)
    phone = payloads.observation("phone", PHONE, evidence_id, observation_id="o-phone")
    email = payloads.observation("email", EMAIL, evidence_id, observation_id="o-email")
    first = flow.send(job, flow.contact(job, evidence_id, [phone]))[1]["results"][0]
    name = payloads.observation("full_name", NAME, evidence_id, observation_id="o-name")
    enriched = payloads.contact(evidence_id, [name, phone, email])  # 3.1.0: the name every time
    second = flow.send(job, flow.event(job, "contact.enriched", enriched))[1]["results"][0]
    assert first["canonical_contact_id"] == second["canonical_contact_id"]
    view = client.get(f"/_stand/jobs/{job.job_id}/contacts")[1]
    assert len(view["contacts"]) == 1
    observed = view["contacts"][0]["observations"]
    assert [o["observation_id"] for o in observed] == ["o-phone", "o-name", "o-email"]
    assert observed[0]["channel_status"] == "published_direct"
    assert flow.job_status(job.job_id)["counts"]["persons"] == 1
    assert flow.job_status(job.job_id)["counts"]["observations"] == 3


def test_contact_on_another_jobs_evidence_is_missing(flow: Flow) -> None:
    first = flow.start("c1")
    evidence_id = flow.page(first, evidence_id="ev-1")
    second = flow.start("c2")
    contact = flow.contact(second, evidence_id, [payloads.observation("phone", PHONE, "ev-1")])
    body = flow.send(second, contact)[1]
    assert body["results"][0]["code"] == "evidence_missing"


def test_enriched_person_without_name_is_refused_with_its_rule(flow: Flow, client: Client) -> None:
    """Contract 3.1.0: a 1.2 worker gets `detail` (rule, observation, field); 1.1 gets no key."""
    status, _ = client.post("/workers/heartbeat", builders.heartbeat_body(
        schema_versions=("1.1", "1.2")))
    assert status == 200
    job = flow.start()
    evidence_id = flow.page(job)
    phone = payloads.observation("phone", PHONE, evidence_id, observation_id="o-phone")
    first = flow.send(job, flow.contact(job, evidence_id, [phone]))[1]["results"][0]
    assert first["detail"] is None, "an accepted event carries detail null for 1.2"
    email = payloads.observation("email", EMAIL, evidence_id, observation_id="o-email")
    refused = flow.send(job, flow.event(job, "contact.enriched",
                                        payloads.contact(evidence_id, [email])))[1]["results"][0]
    assert (refused["status"], refused["code"]) == ("rejected", "invalid_input")
    assert refused["detail"]["rule"] == "person_without_name"
    assert (refused["detail"]["observation_id"], refused["detail"]["field"]) == (
        "o-email", "email")
    client.post("/workers/heartbeat", builders.heartbeat_body())
    other = flow.send(job, flow.contact(job, evidence_id, [payloads.observation(
        "phone", PHONE, evidence_id)]))[1]["results"][0]
    assert "detail" not in other, "a 1.1 worker gets the 3.0.0 shape"
