"""Company-level canonical contacts, known_contacts in claim, change_kind and supersedes."""

from __future__ import annotations

from contract_server.tests import builders
from contract_server.tests.client import Client
from contract_server.tests.flow import Flow
from contract_server.tests.rerun import (
    LATER_STAMP,
    MOVED_PAGE,
    NEW_PHONE,
    PHONE,
    SWITCHBOARD,
    at,
    company_contacts,
    contact_of,
    first_job,
    obs,
    observations,
    rejection,
    rerun,
)

EMAIL = "anna.virtanen@example.fi"


def test_same_person_in_two_jobs_is_one_canonical_contact(flow: Flow, client: Client) -> None:
    known = first_job(flow)
    job, _ = rerun(flow)
    ev = flow.page(job, evidence_id="ev-2")
    name = obs("full_name", "anna  VIRTANEN", ev, "o2-name", quote="Anna Virtanen")
    email = obs("email", EMAIL, ev, "o2-email")
    org = obs("phone", "+358 (9) 555 0100", ev, "o2-switch", quote=SWITCHBOARD, binding="caption")
    body = flow.send(
        job,
        flow.contact(job, ev, [name], entity_id="p-7"),
        flow.contact(job, ev, [email], entity_id="p-7"),
        flow.contact(job, ev, [org], entity_type="organization_channel", entity_id="sw"),
    )[1]
    ids = [r["canonical_contact_id"] for r in body["results"]]
    assert ids == [known.person_id, known.person_id, known.org_id]
    contacts = company_contacts(client)
    assert len(contacts) == 2
    person = contact_of(client, known.person_id)
    assert person["job_ids"] == [known.job.job_id, job.job_id]
    assert list(observations(person)) == ["o-name", "o-phone", "o2-name", "o2-email"]
    job_view = client.get(f"/_stand/jobs/{job.job_id}/contacts")[1]
    assert [c["canonical_contact_id"] for c in job_view["contacts"]] == ids[1:]
    counts = flow.job_status(job.job_id)["counts"]
    assert (counts["persons"], counts["organization_channels"], counts["observations"]) == (1, 1, 3)
    assert flow.job_status(known.job.job_id)["counts"]["observations"] == 3


def test_person_without_a_name_stays_per_job(flow: Flow) -> None:
    first = flow.start("c1")
    ev = flow.page(first)
    one = flow.send(first, flow.contact(first, ev, [obs("phone", PHONE, ev, "a")]))[1]
    second, _ = rerun(flow)
    ev2 = flow.page(second)
    two = flow.send(second, flow.contact(second, ev2, [obs("phone", PHONE, ev2, "b")]))[1]
    assert one["results"][0]["canonical_contact_id"] != two["results"][0]["canonical_contact_id"]


def test_claim_returns_known_contacts_of_other_jobs(flow: Flow) -> None:
    known = first_job(flow, finish=False)
    info = [obs("email", "info@example.fi", "ev-1", "o-info")]
    kind = {"entity_type": "unassigned_channel", "entity_id": "u"}
    unassigned = flow.contact(known.job, "ev-1", info, **kind)
    again = at(flow.contact(known.job, "ev-1", [obs("phone", PHONE, "ev-1", "o-phone-2")]))
    results = flow.send(known.job, unassigned, again)[1]["results"]
    assert [r["status"] for r in results] == ["accepted", "accepted"]
    flow.finish(known.job)
    _, item = rerun(flow)
    by_id = {c["canonical_contact_id"]: c for c in item["known_contacts"]}
    assert list(by_id) == [known.person_id, known.org_id]
    person, org = by_id[known.person_id], by_id[known.org_id]
    assert person["entity_type"] == "person"
    assert person["fields"] == {"full_name": "Anna Virtanen", "phone": PHONE}, "ANSWERS_S5 1"
    assert (person["last_seen_at"], person["channel_status"]) == (LATER_STAMP, "published_direct")
    assert (org["entity_type"], org["channel_status"]) == (
        "organization_channel",
        "published_general",
    )
    assert org["fields"] == {"phone": SWITCHBOARD}


def test_reconfirmed_value_adds_no_row(flow: Flow, client: Client) -> None:
    known = first_job(flow)
    job, _ = rerun(flow)
    ev = flow.page(job)
    same = [
        obs("full_name", "Anna Virtanen", ev, "o2-name", kind="reconfirmed"),
        obs("phone", PHONE, ev, "o2-phone", kind="reconfirmed"),
    ]
    event = at(flow.contact(job, ev, same))
    result = flow.send(job, event)[1]["results"][0]
    assert (result["status"], result["channel_status"]) == ("accepted", "published_direct")
    assert result["canonical_contact_id"] == known.person_id
    repeat = flow.contact(job, ev, [obs("phone", PHONE, ev, "o2-phone", kind="reconfirmed")])
    assert flow.send(job, repeat)[1]["results"][0]["status"] == "accepted"
    person = contact_of(client, known.person_id)
    rows = observations(person)
    assert list(rows) == ["o-name", "o-phone"]
    assert rows["o-phone"]["last_confirmed_at"] == LATER_STAMP
    assert rows["o-phone"]["history"] == [
        {
            "date": LATER_STAMP,
            "observation_id": "o2-phone",
            "kind": "reconfirmed",
            "value": PHONE,
            "run_id": job.lease["run_id"],
        }
    ]
    assert person["last_seen_at"] == LATER_STAMP
    moved = flow.page(job, MOVED_PAGE)
    other = obs("phone", NEW_PHONE, moved, "o2-new", kind="reconfirmed")
    assert flow.send(job, flow.contact(job, moved, [other]))[1]["results"][0]["code"] is None
    assert "o2-new" in observations(contact_of(client, known.person_id))


def test_changed_supersedes_the_old_value(flow: Flow, client: Client) -> None:
    known = first_job(flow)
    job, _ = rerun(flow)
    ev = flow.page(job, MOVED_PAGE)
    moved = [
        obs("full_name", "Anna Virtanen", ev, "o2-name", kind="reconfirmed"),
        obs("phone", NEW_PHONE, ev, "o2-phone", kind="changed", supersedes="o-phone"),
    ]
    result = flow.send(job, at(flow.contact(job, ev, moved)))[1]["results"][0]
    assert (result["status"], result["canonical_contact_id"]) == ("accepted", known.person_id)
    rows = observations(contact_of(client, known.person_id))
    assert rows["o-phone"]["superseded_by"] == "o2-phone"
    assert [(h["kind"], h["observation_id"], h["value"]) for h in rows["o-phone"]["history"]] == [
        ("changed", "o2-phone", NEW_PHONE)
    ]
    assert rows["o2-phone"]["superseded_by"] is None
    _, item = rerun(flow, reason="again")
    person = next(c for c in item["known_contacts"] if c["canonical_contact_id"] == known.person_id)
    assert person["fields"]["phone"] == NEW_PHONE


def test_invalid_supersedes_is_rejected(flow: Flow, client: Client) -> None:
    known = first_job(flow)
    flow.batch(builders.company("c9"))
    stranger = flow.claim(max_jobs=1)[0]
    assert stranger["known_contacts"] == []
    job, _ = rerun(flow)
    ev = flow.page(job, MOVED_PAGE)
    name = obs("full_name", "Anna Virtanen", ev, "o2-name")
    cases = [
        ("missing", "phone", "is unknown"),
        ("o-name", "phone", "is field 'full_name', not 'phone'"),
        ("o-switch", "phone", "belongs to another canonical contact"),
    ]
    for target, field, reason in cases:
        bad = obs(field, NEW_PHONE, ev, f"bad-{target}", kind="changed", supersedes=target)
        result = flow.send(job, flow.contact(job, ev, [name, bad]))[1]["results"][0]
        assert (result["status"], result["code"]) == ("rejected", "invalid_input"), target
        assert reason in rejection(client, job)["detail"]
    assert list(observations(contact_of(client, known.person_id))) == ["o-name", "o-phone"]
