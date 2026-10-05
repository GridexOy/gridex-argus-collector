"""Owner decision 05.10.2026 (ANSWERS_S5): country, department, office_name, address
and fax only as `field="extra"` with that `extra_label`, with a quote."""

from __future__ import annotations

import pytest

from contract_server.tests.client import Client
from contract_server.tests.flow import Flow
from contract_server.tests.rerun import company_contacts, first_job, obs, rejection, rerun


def test_extra_with_a_label_is_accepted_and_keyed_by_it(flow: Flow, client: Client) -> None:
    known = first_job(flow, finish=False)
    ev = flow.page(known.job, evidence_id="ev-x")
    sales = obs("extra", "Sales", ev, "o-dept", extra_label="department", quote="Sales")
    body = flow.send(known.job, flow.contact(known.job, ev, [sales]))[1]
    assert body["results"][0]["status"] == "accepted", body
    assert body["results"][0]["channel_status"] is None, "an extra field is no channel"
    assert flow.finish(known.job)[0] == 200
    _, claimed = rerun(flow)
    anna = next(k for k in claimed["known_contacts"] if k["entity_type"] == "person")
    assert anna["fields"]["department"] == "Sales", "keyed by the extra_label (ANSWERS_S5 1)"
    person = next(c for c in company_contacts(client) if c["entity_type"] == "person")
    assert person["canonical_contact_id"] == known.person_id


@pytest.mark.parametrize("field", ["country", "department", "office_name", "address", "fax"])
def test_a_direct_extra_field_is_invalid_input(flow: Flow, client: Client, field: str) -> None:
    job = flow.start(company_id=f"c-{field}")
    ev = flow.page(job, evidence_id=f"ev-{field}")
    direct = obs(field, "Sales", ev, f"o-{field}", quote="Sales")
    body = flow.send(job, flow.contact(job, ev, [direct]))[1]
    assert body["results"][0]["status"] == "rejected"
    row = rejection(client, job)
    assert body["results"][0]["code"] == "invalid_input", body["results"][0]
    assert "extra_label" in row["detail"], row


def test_extra_without_a_label_is_invalid_input(flow: Flow, client: Client) -> None:
    job = flow.start(company_id="c-nolabel")
    ev = flow.page(job, evidence_id="ev-nolabel")
    body = flow.send(job, flow.contact(job, ev, [obs("extra", "Sales", ev, "o-nl")]))[1]
    assert body["results"][0]["status"] == "rejected"
    assert "needs an extra_label" in rejection(client, job)["detail"]
