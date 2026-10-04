"""Effects of the non-contact event types (contacts.py and finish.py do the rest).

State changes (job state, stage) happen only when the batch `applies`;
data (progress snapshots, sources, records, model calls) is stored either way.
"""

from __future__ import annotations

from collections.abc import Callable

from contract_server import contacts, finish
from contract_server.event_context import Batch, Outcome
from contract_server.state import LEASE_STATES
from contract_server.util import Json

Applier = Callable[[Batch, Json], Outcome]
PROGRESS_FIELDS = ("stage", "counts", "coverage", "active_seconds", "transport_state")


def started(batch: Batch, event: Json) -> Outcome:
    if batch.applies:
        if batch.job["state"] in LEASE_STATES:
            batch.job["state"] = "running"
        batch.job["stage"] = event["payload"]["stage"]
    return Outcome(state_applied=batch.applies)


def progress(batch: Batch, event: Json) -> Outcome:
    payload = event["payload"]
    batch.run["progress"] = {name: payload[name] for name in PROGRESS_FIELDS}
    batch.job["counts_snapshot"] = payload["counts"]
    if batch.applies:
        batch.job["stage"] = payload["stage"]
    return Outcome(state_applied=batch.applies)


def needs_attention(batch: Batch, event: Json) -> Outcome:
    payload = event["payload"]
    batch.run["attention"].append(payload["gap"])
    batch.job["counts_snapshot"] = payload["counts"]
    if batch.applies and batch.job["state"] in LEASE_STATES:
        batch.job["state"] = "needs_attention"
    return Outcome(state_applied=batch.applies)


def source(batch: Batch, event: Json) -> Outcome:
    batch.record("sources", event, dict(event["payload"]))
    return Outcome(state_applied=batch.applies)


def stored(batch: Batch, event: Json) -> Outcome:
    batch.record("records", event, {"payload": event["payload"]})
    return Outcome(state_applied=batch.applies)


def model_called(batch: Batch, event: Json) -> Outcome:
    usage = event["payload"]["usage"]
    row: Json = {name: usage[name] for name in usage}
    row["source_ids"] = event["payload"]["source_ids"]
    batch.record("model_calls", event, row)
    return Outcome(state_applied=batch.applies)


APPLIERS: dict[str, Applier] = {
    "job.started": started,
    "job.progress": progress,
    "job.needs_attention": needs_attention,
    "job.finished": finish.apply,
    "source.discovered": source,
    "source.processed": source,
    "source.blocked": source,
    "contact.observed": contacts.apply,
    "contact.enriched": contacts.apply,
    "contact.merge_proposed": stored,
    "contact.freshness": stored,
    "route.recorded": stored,
    "route.verified": stored,
    "model.called": model_called,
}
