"""Shared types of the events pipeline: the request-wide `Batch` and an `Outcome`."""

from __future__ import annotations

from dataclasses import dataclass

from contract_server.context import Stand
from contract_server.leases import FULL
from contract_server.util import Json


@dataclass
class Batch:
    """One POST /events request: one job, one run, one token's rights."""

    stand: Stand
    job: Json
    run: Json
    rights: str
    gap: bool = False
    next_run_scheduled: bool = False

    @property
    def state(self) -> Json:
        return self.stand.state

    @property
    def applies(self) -> bool:
        """Whether accepted events may change job state (not drain-only, not an old run)."""
        return self.rights == FULL and self.job["current_run_id"] == self.run["run_id"]

    def record(self, kind: str, event: Json, extra: Json) -> None:
        """Append a stored row (model_calls, sources, records) tagged with job/run/event."""
        row: Json = {
            "job_id": self.job["job_id"],
            "run_id": self.run["run_id"],
            "event_id": event["event_id"],
            "type": event["type"],
        }
        row.update(extra)
        self.state[kind].append(row)


@dataclass
class Outcome:
    """What one new event did. `record=False` = not stored, seq not advanced."""

    status: str = "accepted"
    code: str | None = None
    detail: str = ""
    record: bool = True
    canonical_contact_id: str | None = None
    channel_status: str | None = None
    state_applied: bool = False


def rejected(code: str, detail: str = "", record: bool = True) -> Outcome:
    return Outcome(status="rejected", code=code, detail=detail, record=record)
