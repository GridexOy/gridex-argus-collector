"""Office entities of the country sections of a page (owner decision 05.10.2026).

Under an opened country heading the office is one entity: its country (the
heading), company name, address, switchboard and general email; the fax is
not a channel (extraction leaves it out). Channels a person card already
took stay with the person. Channels outside every section are handled as
before (organization / office / unassigned channel by their line).
"""

from __future__ import annotations

from argus_collector.extraction import contract as extraction
from argus_collector.normalization import contract as norm
from argus_collector.walk.context import PageContext
from argus_collector.walk.entities import BINDING_CAPTION, CONFIRMED, PageBuilder
from argus_collector.walk.sink import AuditEntry, FieldFinding

OFFICE = "office"
BINDING_CARD = "card"


def _text_field(value: str, quote: str, start: int, end: int) -> extraction.VerifiedField:
    return extraction.VerifiedField(value, quote, start, end, "text")


def _channel_field(channel: extraction.Channel) -> extraction.VerifiedField:
    span = channel.span
    assert span is not None
    return extraction.VerifiedField(channel.value, span.quote, span.start, span.end,
                                    channel.locator)


def _unclaimed(page: PageBuilder, section: extraction.Section,
               channels: list[extraction.Channel]) -> list[extraction.Channel]:
    claimed = page.state.cp.claimed
    return [
        c for c in channels
        if c.span is not None and section.start <= c.span.start < section.end
        and f"{c.kind}|{c.value}" not in claimed
    ]


def _office(page: PageBuilder, index: int, section: extraction.Section,
            channels: list[extraction.Channel]) -> None:
    lines = extraction.office_lines(page.source.text, section)
    if not channels and lines.address is None:
        return
    title = lines.name.quote if lines.name else section.heading.quote
    key = f"{OFFICE}:{section.country}:{norm.normalize_text(title).casefold()}"
    head = section.heading
    parts: list[tuple[str, extraction.VerifiedField, str, str]] = [
        ("country", _text_field(section.country, head.quote, head.start, head.end),
         BINDING_CAPTION, ""),
    ]
    if lines.name is not None:
        named = lines.name
        value = norm.normalize_text(named.quote)
        parts.append(("office_name", _text_field(value, named.quote, named.start, named.end),
                      BINDING_CARD, "office_name"))
    if lines.address is not None:
        addr = lines.address
        value = ", ".join(line.strip() for line in addr.quote.splitlines() if line.strip())
        parts.append(("address", _text_field(value, addr.quote, addr.start, addr.end),
                      BINDING_CARD, "address"))
    parts += [(c.kind, _channel_field(c), BINDING_CARD, c.kind) for c in channels]
    new: list[FieldFinding] = []
    for name, vf, binding, audited in parts:
        found, obs_id = page.finding(key, name, vf, binding, CONFIRMED)
        if found is not None:
            new.append(found)
        if audited:
            page.audit.append(AuditEntry(f"office[{index}].{audited}", (obs_id,), vf.quote))
        if name in ("phone", "email"):
            page.claim(name, vf.value, obs_id)
    page.add_entity(key, OFFICE, new)


def add_offices(page: PageBuilder, context: PageContext,
                channels: list[extraction.Channel]) -> None:
    for index, section in enumerate(context.sections):
        _office(page, index, section, _unclaimed(page, section, channels))
