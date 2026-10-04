"""Small shared helpers: JSON alias, time formatting, hashing, ids, hosts."""

from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

Json = dict[str, Any]

DRAIN_SECONDS = 24 * 3600.0
OFFLINE_AFTER_SECONDS = 90.0
TERMINAL_STATES = frozenset({"completed", "partial", "failed", "cancelled"})


def iso(ts: float) -> str:
    """Epoch seconds -> RFC 3339 UTC string (second precision)."""
    return datetime.fromtimestamp(ts, UTC).isoformat(timespec="seconds")


def iso_or_none(ts: float | None) -> str | None:
    return None if ts is None else iso(ts)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_hash(value: Any) -> str:
    """sha256 of the canonical JSON form: the idempotency fingerprint of a payload."""
    return sha256_hex(canonical_json(value).encode("utf-8"))


def new_id() -> str:
    return str(uuid.uuid4())


def new_token() -> str:
    """Opaque execution token."""
    return secrets.token_urlsafe(24)


def normalize_host(host: str) -> str:
    """K7 host form: lowercase, no trailing dot, leading `www.` stripped."""
    value = host.strip().lower().rstrip(".")
    return value[4:] if value.startswith("www.") else value


def url_host(url: str) -> str:
    try:
        hostname = urlsplit(url).hostname
    except ValueError:
        return ""
    return normalize_host(hostname or "")


def caller_key(token: str) -> str:
    """Scope key of a system caller, without storing the token itself."""
    return sha256_hex(token.encode("utf-8"))[:16]
