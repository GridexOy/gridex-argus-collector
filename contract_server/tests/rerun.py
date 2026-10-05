"""Helpers for company history tests: a first job with known contacts, then reruns."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from contract_server.tests import builders, payloads
from contract_server.tests.client import Client
from contract_server.tests.flow import Flow, Job
from contract_server.util import Json

PHONE = "+358 40 123 4567"
NEW_PHONE = "+358 50 765 4321"
SWITCHBOARD = "+358 9 555 0100"
LATER = "2026-10-05T09:00:00Z"
LATER_STAMP = "2026-10-05T09:00:00+00:00"
FIRST_STAMP = "2026-10-04T12:00:00+00:00"
MOVED_PAGE = builders.PAGE.replace(PHONE, NEW_PHONE)


@dataclass
class Known:
    """The first job of company c1: Anna (person e1) and the switchboard (org o1)."""

    job: Job
    person_id: str
    org_id: str


def obs(field: str, value: str, evidence_id: str, oid: str, **extra: Any) -> Json:
    """An observation with a fixed id; `kind`/`supersedes` set change_kind/supersedes."""
    body = payloads.observation(field, value, evidence_id, observation_id=oid)
    if "kind" in extra:
        body["change_kind"] = extra.pop("kind")
    if "supersedes" in extra:
        body["supersedes_observation_id"] = extra.pop("supersedes")
    body.update(extra)
    return body


def at(event: Json, occurred_at: str = LATER) -> Json:
    event["occurred_at"] = occurred_at
    return event


def first_job(flow: Flow, finish: bool = True) -> Known:
    job = flow.start("c1")
    ev = flow.page(job, evidence_id="ev-1")
    anna = [
        obs("full_name", "Anna Virtanen", ev, "o-name"),
        obs("phone", PHONE, ev, "o-phone"),
    ]
    org = [obs("phone", SWITCHBOARD, ev, "o-switch", binding="caption")]
    body = flow.send(
        job,
        flow.contact(job, ev, anna),
        flow.contact(job, ev, org, entity_type="organization_channel", entity_id="o1"),
    )[1]
    assert [r["status"] for r in body["results"]] == ["accepted", "accepted"], body
    if finish:
        assert flow.finish(job)[0] == 200
    person_id, org_id = (r["canonical_contact_id"] for r in body["results"])
    return Known(job, person_id, org_id)


def rerun(flow: Flow, company_id: str = "c1", reason: str = "freshness") -> tuple[Job, Json]:
    """A new batch for an existing company; returns the claimed job and its ClaimedJob."""
    flow.batch(builders.company(company_id, rerun_reason=reason))
    item = flow.claim(max_jobs=1)[0]
    return Job(item["job"]["job_id"], company_id, item["lease"]), item


def company_contacts(client: Client, company_id: str = "c1") -> list[Json]:
    status, body = client.get(f"/_stand/companies/{company_id}/contacts")
    assert status == 200, body
    contacts: list[Json] = body["contacts"]
    return contacts


def contact_of(client: Client, contact_id: str, company_id: str = "c1") -> Json:
    found = [
        c for c in company_contacts(client, company_id) if c["canonical_contact_id"] == contact_id
    ]
    assert len(found) == 1
    return found[0]


def observations(contact: Json) -> dict[str, Json]:
    return {o["observation_id"]: o for o in contact["observations"]}


def rejection(client: Client, job: Job) -> Json:
    rows: list[Json] = client.get(f"/_stand/jobs/{job.job_id}/contacts")[1]["rejected"]
    return rows[-1]
