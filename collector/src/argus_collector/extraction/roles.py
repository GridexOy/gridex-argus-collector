"""Role of a channel that no person card claims (TZ_SELAIN section 8.11).

A footer number is the company's, not every person's: unclaimed channels
become `organization_channel` (generic mailbox, switchboard line, JSON-LD
Organization), `office` (the line names an office) or `unassigned_channel`
(nothing says whose it is: the server shows it as `inferred`, section 9.4).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from argus_collector.extraction import repository as tables
from argus_collector.extraction.service import KIND_EMAIL, Channel

ENTITY_ORGANIZATION = "organization_channel"
ENTITY_OFFICE = "office"
ENTITY_UNASSIGNED = "unassigned_channel"
BINDING_JSON = "json_object"
BINDING_CAPTION = "caption"
BINDING_PROXIMITY = "proximity_only"
BINDING_NONE = "none"
LOCAL_SPLIT = re.compile(r"[.\-_+]")


@dataclass(frozen=True)
class ChannelRole:
    entity_type: str
    binding: str


def _line_of(channel: Channel, text: str) -> str:
    if channel.span is None:
        return ""
    start = text.rfind("\n", 0, channel.span.start) + 1
    end = text.find("\n", channel.span.end)
    return text[start : end if end >= 0 else len(text)].lower()


def _has_word(line: str, words: tuple[str, ...]) -> bool:
    return any(re.search(rf"(?<![a-zäöå]){re.escape(w)}(?![a-zäöå])", line) for w in words)


def classify_unattached(channel: Channel, text: str) -> ChannelRole:
    """Entity type and binding of a channel that belongs to no verified person."""
    if channel.locator.startswith("jsonld:"):
        return ChannelRole(ENTITY_ORGANIZATION, BINDING_JSON)
    line = _line_of(channel, text)
    if line and _has_word(line, tables.OFFICE_WORDS):
        return ChannelRole(ENTITY_OFFICE, BINDING_CAPTION)
    if channel.kind == KIND_EMAIL:
        local = channel.value.split("@", 1)[0]
        if LOCAL_SPLIT.split(local)[0] in tables.GENERIC_LOCAL_PARTS:
            binding = BINDING_CAPTION if line else BINDING_PROXIMITY
            return ChannelRole(ENTITY_ORGANIZATION, binding)
        return ChannelRole(ENTITY_UNASSIGNED, BINDING_NONE)
    if line and _has_word(line, tables.ORGANIZATION_PHONE_WORDS):
        return ChannelRole(ENTITY_ORGANIZATION, BINDING_CAPTION)
    return ChannelRole(ENTITY_UNASSIGNED, BINDING_NONE)
