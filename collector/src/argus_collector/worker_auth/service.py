"""Pure logic of worker_auth: masking, connection JSON shape, the pairing key.

The pairing key is one string ARGUS gives the owner:
`argus://pair?url=<ARGUS address>&worker=<worker_id>&token=<token>`. Values
are percent-decoded, a `+` stays a `+` (tokens may be base64). The address
must be https; plain http is accepted only for this PC (the local
contract_server stand). A trailing `/api/collector` is dropped, the panel
adds it itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import unquote, urlsplit, urlunsplit

MASK_VISIBLE = 4
PAIR_SCHEME = "argus"
PAIR_ACTION = "pair"
PAIR_FIELDS = ("url", "worker", "token")
API_SUFFIX = "/api/collector"
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})

REASON_FORMAT = "format"  # not argus://pair?...
REASON_MISSING = "missing"  # a field is absent or empty
REASON_DUPLICATE = "duplicate"  # a field is given twice
REASON_CHARACTERS = "characters"  # whitespace or control characters inside a value
REASON_URL = "url"  # the address is not an http(s) URL with a host
REASON_HTTPS = "https"  # plain http to another machine


@dataclass(frozen=True)
class SavedConnection:
    base_url: str
    worker_id: str


@dataclass(frozen=True)
class PairingKey:
    base_url: str
    worker_id: str
    token: str


class PairingKeyError(ValueError):
    """Why a pasted pairing key is refused (`reason`, and the field it is about)."""

    def __init__(self, reason: str, field: str = "") -> None:
        super().__init__(f"pairing key refused: {reason} {field}".strip())
        self.reason = reason
        self.field = field


def mask_token(token: str) -> str:
    """Only the last 4 characters, for logs and the screen (TZ_TANDEM A1.2)."""
    if len(token) <= MASK_VISIBLE:
        return "*" * len(token)
    return "*" * (len(token) - MASK_VISIBLE) + token[-MASK_VISIBLE:]


def is_loopback(address: str) -> bool:
    """The address points at this PC (127.0.0.1, localhost, ::1)."""
    try:
        host = urlsplit(address if "://" in address else "//" + address).hostname
    except ValueError:
        return False
    return (host or "") in LOOPBACK_HOSTS


def connection_to_mapping(connection: SavedConnection) -> dict[str, str]:
    return {"base_url": connection.base_url, "worker_id": connection.worker_id}


def connection_from_mapping(data: dict[str, object]) -> SavedConnection | None:
    base_url, worker_id = data.get("base_url"), data.get("worker_id")
    if not isinstance(base_url, str) or not isinstance(worker_id, str):
        return None
    if not base_url or not worker_id:
        return None
    return SavedConnection(base_url=base_url, worker_id=worker_id)


def _query_values(query: str) -> dict[str, list[str]]:
    """`a=1&b=2` -> {a: [1], b: [2]}; percent-decoded, `+` kept as is."""
    out: dict[str, list[str]] = {}
    for part in query.split("&"):
        if part:
            name, _, value = part.partition("=")
            out.setdefault(unquote(name).strip().lower(), []).append(unquote(value).strip())
    return out


def _field(values: dict[str, list[str]], name: str) -> str:
    items = values.get(name, [])
    if len(items) > 1:
        raise PairingKeyError(REASON_DUPLICATE, name)
    if not items or not items[0]:
        raise PairingKeyError(REASON_MISSING, name)
    if any(ch.isspace() or ord(ch) < 32 or ord(ch) == 127 for ch in items[0]):
        raise PairingKeyError(REASON_CHARACTERS, name)
    return items[0]


def _base_url(url: str) -> str:
    try:
        parts = urlsplit(url)
        host = parts.hostname or ""
    except ValueError as exc:
        raise PairingKeyError(REASON_URL, "url") from exc
    if parts.scheme not in ("http", "https") or not host or parts.username or parts.query:
        raise PairingKeyError(REASON_URL, "url")
    if parts.scheme == "http" and host not in LOOPBACK_HOSTS:
        raise PairingKeyError(REASON_HTTPS, "url")
    path = parts.path.rstrip("/")
    if path.endswith(API_SUFFIX):
        path = path[: -len(API_SUFFIX)]
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


def parse_pairing_key(text: str) -> PairingKey:
    """The pasted string -> PairingKey; anything else raises PairingKeyError."""
    try:
        parts = urlsplit(text.strip())
    except ValueError as exc:
        raise PairingKeyError(REASON_FORMAT) from exc
    if (parts.scheme.lower(), parts.netloc.lower()) != (PAIR_SCHEME, PAIR_ACTION):
        raise PairingKeyError(REASON_FORMAT)
    if parts.path not in ("", "/") or not parts.query:
        raise PairingKeyError(REASON_FORMAT)
    values = _query_values(parts.query)
    url, worker, token = (_field(values, name) for name in PAIR_FIELDS)
    return PairingKey(_base_url(url), worker, token)
