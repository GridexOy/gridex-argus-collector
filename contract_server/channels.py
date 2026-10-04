"""K3 channel status derived server-side (TZ_SELAIN 9.4); workers never set it."""

from __future__ import annotations

from contract_server.util import Json

CHANNEL_FIELDS = frozenset({"phone", "email", "mobile", "fax"})
CHANNEL_PREFIXES = ("phone_", "email_")
NOT_A_CHANNEL = frozenset({"email_pattern"})
STRUCTURED_BINDINGS = frozenset({"card", "table_row", "json_object", "caption"})
GENERAL_ENTITIES = frozenset({"organization_channel", "office", "department"})
STRENGTH = ("published_direct", "published_general", "inferred", "stale")


def is_channel(field: str) -> bool:
    """phone, email, mobile, fax, phone_*, email_* -- except email_pattern."""
    if field in NOT_A_CHANNEL:
        return False
    return field in CHANNEL_FIELDS or field.startswith(CHANNEL_PREFIXES)


def channel_status(entity_type: str, observation: Json) -> str | None:
    """Status of one observation; None for non-channel fields (incl. email_pattern)."""
    if not is_channel(observation["field"]):
        return None
    binding = observation["binding"]
    extraction = observation["extraction_status"]
    if extraction == "historical":
        return "stale"
    if entity_type == "person":
        if extraction == "confirmed" and binding in STRUCTURED_BINDINGS:
            return "published_direct"
        return "inferred"
    if entity_type in GENERAL_ENTITIES and binding != "none" and extraction == "confirmed":
        return "published_general"
    return "inferred"


def strongest(statuses: list[str | None]) -> str | None:
    """published_direct > published_general > inferred > stale; None when no channel."""
    ranked = [STRENGTH.index(status) for status in statuses if status in STRENGTH]
    return STRENGTH[min(ranked)] if ranked else None
