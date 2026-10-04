"""Findings of one page: persons (with DOM binding), unclaimed channels, field audit.

Ids are stable within the job (`WalkState.uid`): a person is the same entity
on every page and in every run; an observation id depends on the value and
the snapshot, so a re-processed page after a restart yields the same ids and
the server de-duplicates. A value already sent is not sent again, but the
page's field audit still maps it to its first observation (FieldAudit,
TZ_SELAIN 8.9: no contact field of a source is dropped silently).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from argus_collector.browser.contract import PersonProbe, ProbeValue
from argus_collector.extraction import contract as extraction
from argus_collector.walk.sink import (
    AuditEntry,
    EntityFinding,
    FieldFinding,
    PageFindings,
    PageSource,
)
from argus_collector.walk.state import WalkState

PERSON = "person"
FIELD_NAME = "full_name"
FIELD_TITLE = "job_title"
STRONG_BINDINGS = ("card", "table_row")
BINDING_ORDER = ("card", "table_row", "proximity_only", "none")


def person_fields(contact: extraction.Contact) -> list[tuple[str, extraction.VerifiedField]]:
    """Probed fields of a person in probe order (title, phone, email)."""
    out = [(FIELD_TITLE, contact.title), ("phone", contact.phone), ("email", contact.email)]
    return [(name, value) for name, value in out if value is not None]


def probes(contacts: list[extraction.Contact]) -> list[PersonProbe]:
    return [
        PersonProbe(
            c.name.quote,
            tuple(
                ProbeValue(vf.quote, name if name != FIELD_TITLE else "text", vf.value)
                for name, vf in person_fields(c)
            ),
        )
        for c in contacts
    ]


def person_key(state: WalkState, contact: extraction.Contact) -> str:
    """Same name = same person, unless both carry different personal emails."""
    base = contact.name.value.casefold()
    email = contact.email.value if contact.email else None
    known = state.cp.entities.get(base, {}).get("email")
    return f"{base}|{email}" if known and email and known != email else base


@dataclass
class _Page:
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


def _status(binding: str) -> str:
    """Card / table row binding confirms a person field; mere proximity does not (8.11)."""
    return "confirmed" if binding in STRONG_BINDINGS else "ambiguous"


def _name_binding(bindings: tuple[str, ...]) -> str:
    for candidate in BINDING_ORDER:
        if candidate in bindings:
            return candidate
    return "none"


def _add_person(
    page: _Page, index: int, contact: extraction.Contact, bindings: tuple[str, ...]
) -> str:
    key = person_key(page.state, contact)
    probed = person_fields(contact)
    name_status = "confirmed" if probed else "ambiguous"  # a bare name proves little
    pairs = [(FIELD_NAME, contact.name, _name_binding(bindings), name_status)]
    for i, (name, vf) in enumerate(probed):
        binding = bindings[i] if i < len(bindings) else "none"
        pairs.append((name, vf, binding, _status(binding)))
    new: list[FieldFinding] = []
    for name, vf, binding, status in pairs:
        found, obs_id = page.finding(key, name, vf, binding, status)
        if found is not None:
            new.append(found)
        if name in ("phone", "email"):
            page.state.cp.claimed[f"{name}|{vf.value}"] = obs_id
        page.audit.append(AuditEntry(f"person[{index}].{name}", (obs_id,), vf.quote))
    page.add_entity(key, PERSON, new)
    return key


def _add_channel(page: _Page, channel: extraction.Channel) -> None:
    claim = f"{channel.kind}|{channel.value}"
    source_field = f"channel:{channel.kind}:{channel.locator}"
    if claim in page.state.cp.claimed:
        page.audit.append(AuditEntry(source_field, (page.state.cp.claimed[claim],), channel.raw))
        return
    role = extraction.classify_unattached(channel, page.source.text)
    key = f"{role.entity_type}:{claim}"
    span = channel.span
    vf = extraction.VerifiedField(
        channel.value,
        span.quote if span else channel.raw,
        span.start if span else -1,
        span.end if span else -1,
        channel.locator,
    )
    found, obs_id = page.finding(key, channel.kind, vf, role.binding, "confirmed")
    page.add_entity(key, role.entity_type, [found] if found else [])
    page.audit.append(AuditEntry(source_field, (obs_id,), channel.raw))


def build_findings(
    state: WalkState,
    source: PageSource,
    contacts: list[extraction.Contact],
    bindings: list[tuple[str, ...]],
    channels: list[extraction.Channel],
) -> tuple[PageFindings, list[str]]:
    """Findings of the page and the person key of each contact (same order)."""
    page = _Page(state, source)
    keys = [
        _add_person(page, i, contact, bindings[i] if i < len(bindings) else ())
        for i, contact in enumerate(contacts)
    ]
    for channel in channels:
        _add_channel(page, channel)
    return PageFindings(source, tuple(page.entities), tuple(page.audit)), keys
