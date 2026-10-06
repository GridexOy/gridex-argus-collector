"""Findings of one page: persons (with DOM binding), offices, unclaimed channels, audit.

A person carries its verified name, title, phone and email, plus context
fields: the department (group heading / tab of its card) and the country
(its country section or the page's `<html lang>` region). Channels of an
opened country section form that country's office (`offices.py`); the
remaining channels become organization / office / unassigned channels.
Ids and the field audit: `entities.py`.
"""

from __future__ import annotations

from argus_collector.browser.contract import PersonBinding, PersonProbe, ProbeValue
from argus_collector.extraction import contract as extraction
from argus_collector.walk import context as ctx
from argus_collector.walk.entities import BINDING_CAPTION, CONFIRMED, PageBuilder, status_of
from argus_collector.walk.offices import add_offices
from argus_collector.walk.patterns import BINDING_NONE, UNCONFIRMED, add_patterns, from_pattern
from argus_collector.walk.sink import (
    AuditEntry,
    FieldFinding,
    PageFindings,
    PageSource,
    extra_label_of,
)
from argus_collector.walk.state import WalkState

PERSON = "person"
FIELD_NAME = "full_name"
FIELD_TITLE = "job_title"
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
                for name, vf in person_fields(c) if not from_pattern(vf)  # last: no shift
            ),
        )
        for c in contacts
    ]


def person_key(state: WalkState, contact: extraction.Contact) -> str:
    """Same name = same person, unless both carry different personal emails."""
    base = contact.name.value.casefold()
    email = contact.email.value if contact.email and not from_pattern(contact.email) else None
    known = state.cp.entities.get(base, {}).get("email")
    return f"{base}|{email}" if known and email and known != email else base


def _name_binding(bindings: tuple[str, ...]) -> str:
    for candidate in BINDING_ORDER:
        if candidate in bindings:
            return candidate
    return "none"


def _context_pairs(
    page: PageBuilder, contact: extraction.Contact, binding: PersonBinding, context: ctx.PageContext
) -> list[tuple[str, extraction.VerifiedField, str, str]]:
    out: list[tuple[str, extraction.VerifiedField, str, str]] = []
    department = ctx.department_field(page.source.text, binding.group, contact, binding.in_panel)
    if department is not None:
        out.append(("department", department, BINDING_CAPTION, CONFIRMED))
    country = ctx.country_field(context, contact.name.start, contact.phone)
    if country is not None:
        out.append(("country", country, BINDING_CAPTION, CONFIRMED))
    return out


def _add_person(
    page: PageBuilder, index: int, contact: extraction.Contact, binding: PersonBinding,
    context: ctx.PageContext,
) -> str:
    key = person_key(page.state, contact)
    probed = person_fields(contact)
    bindings = binding.values
    proven = [vf for _name, vf in probed if not from_pattern(vf)]
    name_status = CONFIRMED if proven else "ambiguous"  # a bare name proves little
    pairs = [(FIELD_NAME, contact.name, _name_binding(bindings), name_status)]
    for i, (name, vf) in enumerate(probed):
        value_binding = bindings[i] if i < len(bindings) and not from_pattern(vf) else BINDING_NONE
        status = UNCONFIRMED if from_pattern(vf) else status_of(value_binding)
        pairs.append((name, vf, value_binding, status))
    pairs += _context_pairs(page, contact, binding, context)
    new: list[FieldFinding] = []
    for name, vf, field_binding, status in pairs:
        found, obs_id = page.finding(key, name, vf, field_binding, status)
        if found is not None:
            new.append(found)
        if name in ("phone", "email"):
            page.claim(name, vf.value, obs_id)
        page.audit.append(AuditEntry(f"person[{index}].{name}", (obs_id,), vf.quote,
                                     extra_label_of(name)))
    if new and all(f.field != FIELD_NAME for f in new):  # 3.1.0: the name in every event
        new.insert(0, page.restated(key, *pairs[0]))
    page.add_entity(key, PERSON, new)
    return key


def _add_channel(
    page: PageBuilder, channel: extraction.Channel, context: ctx.PageContext
) -> None:
    claim = f"{channel.kind}|{channel.value}"
    source_field = f"channel:{channel.kind}:{channel.locator}"
    audited = extra_label_of(channel.kind)
    if claim in page.state.cp.claimed:
        claimed = (page.state.cp.claimed[claim],)
        page.audit.append(AuditEntry(source_field, claimed, channel.raw, audited))
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
    found, obs_id = page.finding(key, channel.kind, vf, role.binding, CONFIRMED)
    new = [found] if found else []
    country = ctx.country_field(context, span.start if span else -1)
    if country is not None:  # the company header in ARGUS keeps other countries apart
        other, other_id = page.finding(key, "country", country, BINDING_CAPTION, CONFIRMED)
        new += [other] if other else []
        page.audit.append(AuditEntry(f"{source_field}.country", (other_id,), country.quote,
                                     extra_label_of("country")))
    page.add_entity(key, role.entity_type, new)
    page.audit.append(AuditEntry(source_field, (obs_id,), channel.raw, audited))


def build_findings(
    state: WalkState,
    source: PageSource,
    contacts: list[extraction.Contact],
    bindings: list[PersonBinding],
    channels: list[extraction.Channel],
    context: ctx.PageContext | None = None,
) -> tuple[PageFindings, list[str]]:
    """Findings of the page and the person key of each contact (same order)."""
    page = PageBuilder(state, source)
    where = context or ctx.PageContext()
    keys = [
        _add_person(page, i, contact, bindings[i] if i < len(bindings) else PersonBinding(()),
                    where)
        for i, contact in enumerate(contacts)
    ]
    add_offices(page, where, channels)
    add_patterns(page, where.patterns)
    for channel in channels:
        _add_channel(page, channel, where)
    return PageFindings(source, tuple(page.entities), tuple(page.audit)), keys
