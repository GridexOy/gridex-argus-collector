"""Pure logic of worker_auth: masking, connection JSON shape."""

from __future__ import annotations

from dataclasses import dataclass

MASK_VISIBLE = 4


@dataclass(frozen=True)
class SavedConnection:
    base_url: str
    worker_id: str


def mask_token(token: str) -> str:
    """Only the last 4 characters, for logs and the screen (TZ_TANDEM A1.2)."""
    if len(token) <= MASK_VISIBLE:
        return "*" * len(token)
    return "*" * (len(token) - MASK_VISIBLE) + token[-MASK_VISIBLE:]


def connection_to_mapping(connection: SavedConnection) -> dict[str, str]:
    return {"base_url": connection.base_url, "worker_id": connection.worker_id}


def connection_from_mapping(data: dict[str, object]) -> SavedConnection | None:
    base_url, worker_id = data.get("base_url"), data.get("worker_id")
    if not isinstance(base_url, str) or not isinstance(worker_id, str):
        return None
    if not base_url or not worker_id:
        return None
    return SavedConnection(base_url=base_url, worker_id=worker_id)
