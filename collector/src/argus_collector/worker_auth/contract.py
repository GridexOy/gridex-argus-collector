"""Single entry point of the `worker_auth` module.

Local, per-user storage of the ARGUS connection: the worker token (DPAPI,
secret) and the address/worker_id the owner typed in (plain, not secret).
Nothing here talks to the network; see `api_client` for that.
"""

from __future__ import annotations

from argus_collector.worker_auth import repository, service
from argus_collector.worker_auth.service import SavedConnection, mask_token

__all__ = [
    "SavedConnection",
    "clear_token",
    "load_connection",
    "load_token",
    "mask_token",
    "save_connection",
    "save_token",
]


def load_connection() -> SavedConnection | None:
    mapping = repository.load_connection_mapping()
    return service.connection_from_mapping(mapping) if mapping is not None else None


def save_connection(base_url: str, worker_id: str) -> None:
    connection = SavedConnection(base_url=base_url, worker_id=worker_id)
    repository.save_connection_mapping(service.connection_to_mapping(connection))


def load_token() -> str | None:
    return repository.load_token()


def save_token(token: str) -> None:
    repository.save_token(token)


def clear_token() -> None:
    repository.clear_token()
