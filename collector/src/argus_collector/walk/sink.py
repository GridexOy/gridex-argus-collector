"""What a walk hands to its sink in job mode (ARGUS20_TZ_TANDEM.md pair A2).

The walk itself never talks to ARGUS: it reports stored pages, findings
(entities with verified fields, binding and status, plus the field audit of
the page), gaps, model calls and its checkpoint to a `WalkSink` — the
scheduler turns them into outbox events. `page_done` runs inside the walk's
own write transaction together with the local `observations` rows, so an
observation and its outbox events are one transaction (TZ_SELAIN 10.2).
"""

from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

from argus_collector.evidence.contract import Snapshot
from argus_collector.models.contract import CallRecord


@dataclass(frozen=True)
class WalkLimits:
    """Run budget (policy max_* minus what the campaign already used)."""

    pages: int
    actions: int
    seconds: float
    states: int


@dataclass(frozen=True)
class WalkGap:
    url: str
    state_key: str
    reason: str  # a Gap.reason of the contract
    detail: str
    resumable: bool


@dataclass(frozen=True)
class FrontierLink:
    url: str
    text: str
    score: int
    parent_url: str


@dataclass
class WalkCheckpoint:
    """Everything a resumed run needs; tabs and scroll positions are not kept (8.14)."""

    last_url: str = ""
    visited: list[str] = field(default_factory=list)
    seen_keys: list[str] = field(default_factory=list)
    frontier: dict[str, FrontierLink] = field(default_factory=dict)
    entities: dict[str, dict[str, str]] = field(default_factory=dict)
    known_obs: dict[str, str] = field(default_factory=dict)
    claimed: dict[str, str] = field(default_factory=dict)
    gaps: list[WalkGap] = field(default_factory=list)
    pages: int = 0
    actions: int = 0
    active_seconds: float = 0.0
    native_language: str = ""

    def to_json(self) -> dict[str, Any]:
        data = asdict(self)
        data["frontier"] = {key: asdict(link) for key, link in self.frontier.items()}
        return data

    @staticmethod
    def from_json(data: dict[str, Any]) -> WalkCheckpoint:
        frontier = {str(k): FrontierLink(**v) for k, v in dict(data.get("frontier", {})).items()}
        return WalkCheckpoint(
            last_url=str(data.get("last_url", "")),
            visited=[str(v) for v in data.get("visited", [])],
            seen_keys=[str(v) for v in data.get("seen_keys", [])],
            frontier=frontier,
            entities={str(k): dict(v) for k, v in data.get("entities", {}).items()},
            known_obs={str(k): str(v) for k, v in data.get("known_obs", {}).items()},
            claimed={str(k): str(v) for k, v in data.get("claimed", {}).items()},
            gaps=[WalkGap(**g) for g in data.get("gaps", [])],
            pages=int(data.get("pages", 0)),
            actions=int(data.get("actions", 0)),
            active_seconds=float(data.get("active_seconds", 0.0)),
            native_language=str(data.get("native_language", "")),
        )


@dataclass(frozen=True)
class PageSource:
    source_id: str
    parent_source_id: str | None
    requested_url: str
    url: str
    state_key: str
    snapshot: Snapshot
    text: str  # canonical text the spans point into


@dataclass(frozen=True)
class FieldFinding:
    observation_id: str
    field: str  # full_name | job_title | phone | email
    raw: str  # the quote as found
    value: str  # normalised value
    start: int  # code-point span in the canonical text; -1 when not in the text
    end: int
    locator: str  # text | href:tel | href:mailto | jsonld:<i>/<ptr> | cfemail
    binding: str  # card | table_row | json_object | caption | proximity_only | none
    status: str  # confirmed | ambiguous


@dataclass(frozen=True)
class EntityFinding:
    entity_id: str
    entity_key: str
    entity_type: str  # person | organization_channel | office | unassigned_channel
    is_new: bool  # contact.observed when new, contact.enriched with new fields otherwise
    fields: tuple[FieldFinding, ...]


@dataclass(frozen=True)
class AuditEntry:
    source_field: str
    observation_ids: tuple[str, ...]
    raw: str


@dataclass(frozen=True)
class PageFindings:
    source: PageSource
    entities: tuple[EntityFinding, ...]
    audit: tuple[AuditEntry, ...]


class WalkSink(Protocol):
    def page_stored(self, conn: sqlite3.Connection, source: PageSource) -> None: ...
    def page_done(self, conn: sqlite3.Connection, findings: PageFindings) -> None: ...
    def gap(self, conn: sqlite3.Connection, gap: WalkGap) -> None: ...
    def model_called(self, conn: sqlite3.Connection, record: CallRecord) -> None: ...
    def checkpoint(self, conn: sqlite3.Connection, checkpoint: WalkCheckpoint) -> None: ...
