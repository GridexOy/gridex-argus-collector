"""contact.freshness: check validation, effects (not_seen keeps the contact), summaries."""

from __future__ import annotations

from contract_server.tests.client import Client
from contract_server.tests.flow import Flow, Job
from contract_server.tests.rerun import (
    LATER,
    LATER_STAMP,
    MOVED_PAGE,
    NEW_PHONE,
    PHONE,
    Known,
    at,
    contact_of,
    first_job,
    obs,
    rejection,
    rerun,
)
from contract_server.util import Json

SUMMARY_KEYS = ("reconfirmed", "changed", "not_seen_in_checked_scope", "not_checked")


def name(evidence_id: str) -> Json:
    """Anna's name again: a person is matched across jobs by its full_name."""
    return obs("full_name", "Anna Virtanen", evidence_id, f"name-{evidence_id}", kind="reconfirmed")


def check(contact_id: str, status: str, observation_id: str | None = None, **kw: str) -> Json:
    return {
        "canonical_contact_id": contact_id,
        "field": kw.get("field", "phone"),
        "status": status,
        "scope_description": "contact pages",
        "evidence_ids": [],
        "checked_at": kw.get("checked_at", LATER),
        "observation_id": observation_id,
    }


def fresh(flow: Flow, job: Job, *checks: Json) -> Json:
    return flow.event(job, "contact.freshness", {"checks": list(checks)})


def summary(**values: int) -> Json:
    body: Json = dict.fromkeys(SUMMARY_KEYS, 0)
    body.update(values)
    return body


def job_view(client: Client, job: Job) -> Json:
    body: Json = client.get(f"/_stand/jobs/{job.job_id}/contacts")[1]
    return body


def test_checks_are_validated(flow: Flow, client: Client) -> None:
    known = first_job(flow)
    stranger = flow.start("c9")
    ev = flow.page(stranger)
    alien = flow.send(stranger, flow.contact(stranger, ev, [obs("phone", PHONE, ev, "x")]))[1]
    alien_id = alien["results"][0]["canonical_contact_id"]
    job, _ = rerun(flow)
    ev2 = flow.page(job)
    again = [name(ev2), obs("phone", PHONE, ev2, "o2-phone", kind="reconfirmed")]
    assert flow.send(job, flow.contact(job, ev2, again))[1]["results"][0]["code"] is None
    cases = [
        (check("nope", "reconfirmed"), "nope is not a contact of company c1"),
        (check(alien_id, "reconfirmed"), "is not a contact of company c1"),
        (check(known.person_id, "reconfirmed", "o-phone"), "o-phone is not sent for"),
        (check(known.person_id, "reconfirmed", "x"), "x is not sent for"),
    ]
    for bad, reason in cases:
        body = flow.send(job, fresh(flow, job, check(known.org_id, "not_checked"), bad))[1]
        result = body["results"][0]
        assert (result["status"], result["code"]) == ("rejected", "invalid_input"), reason
        assert reason in rejection(client, job)["detail"]
    good = fresh(flow, job, check(known.person_id, "reconfirmed", "o2-phone"))
    assert flow.send(job, good)[1]["results"][0]["status"] == "accepted"
    assert [c["observation_id"] for c in job_view(client, job)["freshness"]] == ["o2-phone"]
    assert contact_of(client, known.org_id)["not_seen"] is None


def checked(flow: Flow) -> tuple[Known, Job]:
    """A rerun that moved Anna's phone and then sent changed / not_seen / not_checked."""
    known = first_job(flow)
    job, item = rerun(flow)
    assert len(item["known_contacts"]) == 2
    ev = flow.page(job, MOVED_PAGE)
    moved = [
        name(ev),
        obs("phone", NEW_PHONE, ev, "o2-phone", kind="changed", supersedes="o-phone"),
    ]
    assert flow.send(job, flow.contact(job, ev, moved))[1]["results"][0]["code"] is None
    event = fresh(
        flow,
        job,
        check(known.person_id, "changed", "o2-phone"),
        check(known.org_id, "not_seen_in_checked_scope"),
        check(known.person_id, "not_checked", field="email"),
    )
    result = flow.send(job, event)[1]["results"][0]
    assert (result["status"], result["state_applied"]) == ("accepted", True)
    return known, job


def test_freshness_effects(flow: Flow, client: Client) -> None:
    known, job = checked(flow)
    run_id = job.lease["run_id"]
    person, org = contact_of(client, known.person_id), contact_of(client, known.org_id)
    assert person["last_seen_at"] == LATER_STAMP
    assert person["history"] == [
        {
            "date": LATER_STAMP,
            "observation_id": "o2-phone",
            "kind": "changed",
            "field": "phone",
            "run_id": run_id,
        }
    ]
    expected = {"checked_at": LATER_STAMP, "scope_description": "contact pages", "run_id": run_id}
    assert org["not_seen"] == expected
    view = job_view(client, job)
    assert [(c["status"], c["run_id"]) for c in view["freshness"]] == [
        ("changed", run_id),
        ("not_seen_in_checked_scope", run_id),
        ("not_checked", run_id),
    ]
    flow.finish(
        job, freshness_summary=summary(changed=1, not_seen_in_checked_scope=1, not_checked=1)
    )
    runs = job_view(client, job)["freshness_runs"]
    assert [(r["run_id"], r["freshness_mismatch"]) for r in runs] == [(run_id, False)]


def test_not_seen_contact_stays_until_seen_again(flow: Flow, client: Client) -> None:
    known, job = checked(flow)
    flow.finish(job)
    third, item = rerun(flow, reason="third")
    assert known.org_id in [c["canonical_contact_id"] for c in item["known_contacts"]]
    assert contact_of(client, known.org_id)["not_seen"] is not None
    ev3 = flow.page(third)
    seen = obs("phone", "+358 9 555 0100", ev3, "o3-switch", kind="reconfirmed")
    later = "2026-10-06T10:00:00Z"
    flow.send(
        third, at(flow.contact(third, ev3, [seen], entity_type="organization_channel"), later)
    )
    org = contact_of(client, known.org_id)
    assert (org["not_seen"], org["last_seen_at"]) == (None, "2026-10-06T10:00:00+00:00")


def test_summary_mismatch_is_noted_not_rejected(flow: Flow, client: Client) -> None:
    known = first_job(flow)
    job, _ = rerun(flow)
    flow.send(job, fresh(flow, job, check(known.person_id, "reconfirmed")))
    status, body = flow.finish(job)
    assert (status, body["results"][0]["status"]) == (200, "accepted")
    run = job_view(client, job)["freshness_runs"][0]
    assert run["freshness_mismatch"] is True
    assert run["freshness_summary"] == summary()
    assert run["freshness_counted"] == summary(reconfirmed=1)


def test_late_freshness_is_recorded_without_effect(flow: Flow, client: Client) -> None:
    known = first_job(flow)
    job, _ = rerun(flow)
    flow.finish(job)
    late = fresh(flow, job, check(known.org_id, "not_seen_in_checked_scope"))
    result = flow.send(job, late)[1]["results"][0]
    assert (result["status"], result["state_applied"]) == ("accepted", False)
    assert contact_of(client, known.org_id)["not_seen"] is None
    assert len(job_view(client, job)["freshness"]) == 1
