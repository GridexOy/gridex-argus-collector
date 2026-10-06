"""Contract 3.1.0 (ARGUS 0.4.24.4): a contact event that arrives before its evidence.

No evidence row with the named `evidence_id`: the event is accepted with
`code: evidence_pending`, `state_applied=false`, its seq is spent, and it waits
here. The upload of the last evidence it names applies it (in the same upload
request); its stored result becomes the outcome (accepted, or a refusal with its
code and detail), so a repeat of the `event_id` answers `duplicate` with it. A repeat
while it waits answers `duplicate` + `evidence_pending`.
"""

from __future__ import annotations

from contract_server.context import Stand
from contract_server.event_context import Batch, Outcome
from contract_server.util import Json

PENDING = "evidence_pending"


def wait(batch: Batch, event: Json, absent: list[str]) -> Outcome:
    batch.state["waiting"][event["event_id"]] = {
        "job_id": batch.job["job_id"], "run_id": batch.run["run_id"], "rights": batch.rights,
        "wire": batch.wire, "evidence_ids": absent, "event": event,
    }
    return Outcome(code=PENDING, detail=f"waits for {', '.join(absent)}")


def release(stand: Stand, evidence_id: str) -> None:
    """Apply the events whose last missing evidence this upload is."""
    from contract_server import contacts, events  # the events pipeline imports this module

    for event_id, item in list(stand.state["waiting"].items()):
        if evidence_id not in item["evidence_ids"]:
            continue
        item["evidence_ids"] = [e for e in item["evidence_ids"] if e != evidence_id]
        if item["evidence_ids"]:
            continue
        del stand.state["waiting"][event_id]
        job, run = stand.state["jobs"][item["job_id"]], stand.state["runs"][item["run_id"]]
        batch = Batch(stand, job, run, item["rights"], wire=item["wire"])
        outcome = contacts.apply(batch, item["event"])
        stored = stand.state["events"][event_id]
        revision = int(stored["result"]["server_revision"])
        stored["result"] = events.result(item["event"], outcome, revision, item["wire"])
        if outcome.status == "accepted":
            job["last_result_at"] = stand.now()
        else:
            stand.state["rejected"].append(events.rejection_row(batch, item["event"], outcome))
