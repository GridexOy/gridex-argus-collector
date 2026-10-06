"""The address pattern a page states, applied to its people (owner 06.10.2026, Reimax).

A person of the page without a printed email gets the address of the first
pattern the page states; the field is unconfirmed with binding `none`, so
ARGUS shows it `inferred` (oletettu), and its quote is the pattern's line. A
printed address always wins. The pattern itself goes as the company's
`email_pattern` field (never an address, RULES K3) on the company's channel
entity (generic mailbox / switchboard) of this page or an earlier one, so a
re-run finds it by that channel and reconfirms it on the same row; without
such a channel, on an `organization_channel` entity of its own.
"""

from __future__ import annotations

from dataclasses import replace

from argus_collector.extraction import contract as extraction
from argus_collector.walk.entities import BINDING_CAPTION, CONFIRMED, PageBuilder
from argus_collector.walk.sink import AuditEntry, FieldFinding

LOCATOR_PATTERN = "pattern"  # VerifiedField.locator of an address built from a pattern
FIELD_PATTERN = "email_pattern"
COMPANY = "organization_channel"
BINDING_NONE, UNCONFIRMED = "none", "ambiguous"


def from_pattern(field: extraction.VerifiedField | None) -> bool:
    return field is not None and field.locator == LOCATOR_PATTERN


def with_pattern(contacts: list[extraction.Contact],
                 patterns: tuple[extraction.EmailPattern, ...]) -> list[extraction.Contact]:
    """Each person without an email gets the address the page's pattern gives the name."""
    if not patterns:
        return contacts
    pattern, out = patterns[0], []
    for contact in contacts:
        built = None if contact.email else extraction.pattern_address(pattern, contact.name.value)
        if built is not None:
            email = extraction.VerifiedField(built, pattern.quote, pattern.start, pattern.end,
                                             LOCATOR_PATTERN)
            contact = replace(contact, email=email)
        out.append(contact)
    return out


def _company_key(page: PageBuilder) -> str | None:
    """The company's channel entity of this page, else of an earlier page."""
    here = next((e.entity_key for e in page.entities if e.entity_type == COMPANY), None)
    return here or next((k for k in page.state.cp.entities if k.startswith(COMPANY + ":")
                         and f"{FIELD_PATTERN}|" not in k), None)


def _join(page: PageBuilder, key: str, found: FieldFinding) -> bool:
    """Add the field to the entity this page already sends under `key`."""
    for i, entity in enumerate(page.entities):
        if entity.entity_key == key:
            page.entities[i] = replace(entity, fields=(*entity.fields, found))
            page.state.cp.entities.setdefault(key, {})[found.field] = found.value
            return True
    return False


def add_patterns(page: PageBuilder, patterns: tuple[extraction.EmailPattern, ...]) -> None:
    """`email_pattern` of the company, quoted from the line that states it."""
    for i, pattern in enumerate(patterns):
        key = _company_key(page) or f"{COMPANY}:{FIELD_PATTERN}|{pattern.value}"
        vf = extraction.VerifiedField(pattern.value, pattern.quote, pattern.start, pattern.end,
                                      "text")
        found, obs_id = page.finding(key, FIELD_PATTERN, vf, BINDING_CAPTION, CONFIRMED)
        if found is not None and not _join(page, key, found):
            page.add_entity(key, COMPANY, [found])
        page.audit.append(AuditEntry(f"{FIELD_PATTERN}[{i}]", (obs_id,), pattern.quote, ""))
