"""Building the findings of one page: stable ids, known values, the field audit.

Ids are stable within the job (`WalkState.uid`): an entity is the same on
every page and in every run; an observation id depends on the value and the
snapshot, so a re-processed page after a restart yields the same ids and the
server de-duplicates. A value already sent is not sent again, but the page's
field audit still maps it to its first observation (FieldAudit, TZ_SELAIN
8.9: no contact field of a source is dropped silently).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from argus_collector.extraction import contract as extraction
from argus_collector.walk.sink import AuditEntry, EntityFinding, FieldFinding, PageSource
from argus_collector.walk.state import WalkState

STRONG_BINDINGS = ("card", "table_row")
BINDING_CAPTION = "caption"
CONFIRMED = "confirmed"


def status_of(binding: str) -> str:
    """Card / table row binding confirms a person field; mere proximity does not (8.11)."""
    return CONFIRMED if binding in STRONG_BINDINGS else "ambiguous"


@dataclass
class PageBuilder:
    state: WalkState
    source: PageSource
    entities: list[EntityFinding] = field(default_factory=list)
    audit: list[AuditEntry] = field(default_factory=list)

    def finding(
        self, key: str, name: str, vf: extraction.VerifiedField, binding: str, status: str
    ) -> tuple[FieldFinding | None, str]:
        """(new finding or None when this value of the entity is known, observation id)."""
        obs_key = f"{key}|{name}|{vf.value}"
        known = self.state.cp.known_obs.get(obs_key)
        if known is not None:
            return None, known
        obs_id = self.state.uid("obs", f"{obs_key}|{self.source.snapshot.evidence_id}")
        self.state.cp.known_obs[obs_key] = obs_id
        found = FieldFinding(
            obs_id, name, vf.quote, vf.value, vf.start, vf.end, vf.locator, binding, status
        )
        return found, obs_id

    def add_entity(self, key: str, kind: str, fields: list[FieldFinding]) -> None:
        if not fields:
            return
        is_new = key not in self.state.cp.entities
        self.state.cp.entities.setdefault(key, {}).update({f.field: f.value for f in fields})
        entity_id = self.state.uid("entity", key)
        self.entities.append(EntityFinding(entity_id, key, kind, is_new, tuple(fields)))

    def claim(self, kind: str, value: str, obs_id: str) -> None:
        """A channel taken by a person or an office is not a separate company channel."""
        self.state.cp.claimed[f"{kind}|{value}"] = obs_id
