"""Route table, bearer auth and dispatch of one HTTP request to its handler.

Worker routes take a worker token (system token -> 401, revoked -> 403);
system routes take a system token (worker token -> 401). Every request runs
under the stand lock after lazy lease expiry; POSTs (and expiries) are saved.
"""

from __future__ import annotations

import re
import sys
import traceback
from collections.abc import Callable
from urllib.parse import unquote, urlsplit

from contract_server import (
    batches,
    claim,
    control,
    events,
    evidence,
    heartbeat,
    reconcile,
    stand_views,
    status,
)
from contract_server.context import Request, Stand
from contract_server.errors import ApiError, not_found
from contract_server.openapi import BASE_PATH
from contract_server.state import expire_leases
from contract_server.util import Json

Handler = Callable[[Stand, Request], tuple[int, Json]]
WORKER, SYSTEM = "worker", "system"
ROUTE_SPECS: tuple[tuple[str, str, str, Handler], ...] = (
    ("POST", BASE_PATH + "/batches", SYSTEM, batches.create),
    ("GET", BASE_PATH + "/batches/{batch_id}", SYSTEM, status.get_batch),
    ("POST", BASE_PATH + "/workers/heartbeat", WORKER, heartbeat.handle),
    ("GET", BASE_PATH + "/workers/{worker_id}/status", SYSTEM, status.get_worker),
    ("POST", BASE_PATH + "/jobs/claim", WORKER, claim.handle),
    ("POST", BASE_PATH + "/jobs/{job_id}/evidence", WORKER, evidence.handle),
    ("POST", BASE_PATH + "/jobs/{job_id}/events", WORKER, events.handle),
    ("POST", BASE_PATH + "/jobs/{job_id}/reconcile", WORKER, reconcile.handle),
    ("POST", BASE_PATH + "/jobs/{job_id}/control", SYSTEM, control.handle),
    ("GET", BASE_PATH + "/jobs/{job_id}", SYSTEM, status.get_job),
    ("GET", "/_stand/jobs/{job_id}/contacts", SYSTEM, stand_views.contacts),
    ("GET", "/_stand/companies/{company_id}/contacts", SYSTEM, stand_views.company_contacts),
    ("GET", "/_stand/evidence/{evidence_id}", SYSTEM, stand_views.evidence),
)


def _compile(template: str) -> re.Pattern[str]:
    return re.compile("^" + re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", template) + "$")


ROUTES = tuple((method, _compile(path), kind, fn) for method, path, kind, fn in ROUTE_SPECS)


def match(method: str, path: str) -> tuple[Handler, str, dict[str, str]]:
    path_known = False
    for route_method, pattern, kind, handler in ROUTES:
        found = pattern.match(path)
        if found is None:
            continue
        path_known = True
        if route_method == method:
            return handler, kind, {k: unquote(v) for k, v in found.groupdict().items()}
    if path_known:
        raise ApiError(405, "invalid_input", f"method {method} not allowed on {path}")
    raise not_found(f"unknown path {path}")


def bearer(headers: dict[str, str]) -> str | None:
    value = headers.get("authorization", "")
    if not value.startswith("Bearer "):
        return None
    return value[len("Bearer ") :].strip() or None


def authorize(stand: Stand, kind: str, headers: dict[str, str]) -> str:
    """The principal: worker_id for worker routes, the token for system routes."""
    token = bearer(headers)
    if kind == SYSTEM:
        if token is not None and stand.registry.is_system(token):
            return token
        raise ApiError(401, "unauthorized", "a system token is required")
    worker_id = stand.registry.resolve(token)
    if worker_id is None:
        raise ApiError(401, "unauthorized", "unknown or missing worker token")
    if stand.registry.is_revoked(worker_id):
        raise ApiError(403, "worker_revoked", f"worker {worker_id} is revoked")
    return worker_id


def _run(stand: Stand, method: str, path: str, req: Request) -> tuple[int, Json]:
    handler, kind, req.params = match(method, path)
    with stand.lock:
        req.principal = authorize(stand, kind, req.headers)
        expired = expire_leases(stand.state, stand.now())
        try:
            return handler(stand, req)
        finally:
            if method != "GET" or expired:
                stand.save()


def dispatch(
    stand: Stand, method: str, raw_path: str, headers: dict[str, str], body: bytes, request_id: str
) -> tuple[int, Json]:
    path = urlsplit(raw_path).path
    req = Request(method, path, {}, headers, body, request_id)
    try:
        return _run(stand, method, path, req)
    except ApiError as exc:
        exc.request_id = request_id
        return exc.status, exc.body()
    except Exception as exc:  # a stand bug must still answer with an Error body
        traceback.print_exc(file=sys.stderr)
        error = ApiError(500, "storage_unavailable", f"internal stand error: {exc!r}")
        error.request_id = request_id
        return error.status, error.body()
