"""contact.freshness: validate every check, keep the record, apply the effects.

A check names a canonical contact of the job's company and, when
`observation_id` is set, an observation of that contact sent in the same run
(else the event is rejected invalid_input). The record is kept either way;
the effects need a batch that applies state: `reconfirmed` -> last_seen_at,
`changed` -> last_seen_at and a contact history entry, `not_seen_in_checked_scope`
-> a `not_seen` mark (the contact stays), `not_checked` -> recorded only.
"""

from __future__ import annotations

from contract_server.event_context import Batch, Outcome, rejected
from contract_server.history import mark_seen
from contract_server.util import Json, stamp

STATUSES = ("reconfirmed", "changed", "not_seen_in_checked_scope", "not_checked")
TYPE = "contact.freshness"


def sent_in_run(contact: Json, observation_id: str, run_id: str) -> bool:
    stored = contact["observations"].get(observation_id) or contact["aliases"].get(observation_id)
    return stored is not None and stored["run_id"] == run_id


def check_error(batch: Batch, index: int, check: Json) -> str | None:
    contact_id = check["canonical_contact_id"]
    contact = batch.state["contacts"].get(contact_id)
    company_id = batch.job["company_id"]
    if contact is None or contact["company_id"] != company_id:
        return f"checks[{index}]: {contact_id} is not a contact of company {company_id}"
    observation_id = check["observation_id"]
    run_id = batch.run["run_id"]
    if observation_id is not None and not sent_in_run(contact, observation_id, run_id):
        return f"checks[{index}]: {observation_id} is not sent for {contact_id} in run {run_id}"
    return None


def effect(batch: Batch, check: Json) -> None:
    contact = batch.state["contacts"][check["canonical_contact_id"]]
    status, when = check["status"], stamp(check["checked_at"])
    if status in ("reconfirmed", "changed"):
        mark_seen(contact, when)
    if status == "changed":
        contact["history"].append(
            {
                "date": when,
                "observation_id": check["observation_id"],
                "kind": "changed",
                "field": check["field"],
                "run_id": batch.run["run_id"],
            }
        )
    elif status == "not_seen_in_checked_scope":
        contact["not_seen"] = {
            "checked_at": when,
            "scope_description": check["scope_description"],
            "run_id": batch.run["run_id"],
        }


def apply(batch: Batch, event: Json) -> Outcome:
    checks = event["payload"]["checks"]
    for index, check in enumerate(checks):
        problem = check_error(batch, index, check)
        if problem is not None:
            return rejected("invalid_input", problem)
    batch.record("records", event, {"payload": event["payload"]})
    if batch.applies:
        for check in checks:
            effect(batch, check)
    return Outcome(state_applied=batch.applies)


def run_checks(state: Json, run_id: str) -> list[Json]:
    """Every accepted check of one run, in arrival order."""
    return [
        check
        for row in state["records"]
        if row["type"] == TYPE and row["run_id"] == run_id
        for check in row["payload"]["checks"]
    ]


def counted(state: Json, run_id: str) -> Json:
    """The run's checks counted like FinishedPayload.freshness_summary."""
    statuses = [check["status"] for check in run_checks(state, run_id)]
    return {status: statuses.count(status) for status in STATUSES}
