"""POST /workers/heartbeat (WorkerBearer): status, lease renewal, commands, acks.

Only the current lease of a job pinned to this worker is renewed; anything
else is reported as mismatch / cancelled / expired. Commands are every
not-yet-acknowledged command queued for this worker, oldest first.
"""

from __future__ import annotations

from datetime import UTC, datetime

from contract_server.context import Request, Stand
from contract_server.errors import ApiError
from contract_server.util import Json, iso

SUPPORTED_SCHEMA_VERSIONS = {"1.1"}
COMMAND_FIELDS = ("command_id", "job_id", "action", "state_revision", "policy_patch")


def record_worker(stand: Stand, worker_id: str, body: Json, now: float) -> None:
    stand.state["workers"][worker_id] = {
        "worker_id": worker_id,
        "last_seen": now,
        "worker_version": body["worker_version"],
        "capabilities": body["capabilities"],
        "collecting": body["collecting"],
        "outbox_pending": body["outbox_pending"],
        "free_job_slots": body["free_job_slots"],
        "browser_available": body["browser_available"],
        "model_available": body["model_available"],
        "active_job_ids": [item["job_id"] for item in body["active_jobs"]],
    }
    stand.registry.record_heartbeat(worker_id, datetime.fromtimestamp(now, UTC))


def apply_acks(state: Json, worker_id: str, acks: list[Json], now: float) -> None:
    for ack in acks:
        command = state["commands"].get(ack["command_id"])
        if command is None or command["worker_id"] != worker_id or command["ack"] is not None:
            continue
        command["ack"] = {"status": ack["status"], "detail": ack["detail"], "at": now}


def _renewal(item: Json, status: str, expires: str | None = None) -> Json:
    return {
        "job_id": item["job_id"],
        "run_id": item["run_id"],
        "status": status,
        "lease_expires_at": expires,
    }


def _is_current_lease(stand: Stand, worker_id: str, item: Json) -> bool:
    job = stand.state["jobs"].get(item["job_id"])
    run = stand.state["runs"].get(item["run_id"])
    return (
        job is not None
        and run is not None
        and run["job_id"] == job["job_id"]
        and job["worker_id"] == worker_id
        and job["current_run_id"] == run["run_id"]
        and run["lease_token"] == item["execution_token"]
        and run["generation"] == item["lease_generation"]
    )


def renew(stand: Stand, worker_id: str, item: Json, now: float) -> Json:
    if not _is_current_lease(stand, worker_id, item):
        return _renewal(item, "mismatch")
    job = stand.state["jobs"][item["job_id"]]
    run = stand.state["runs"][item["run_id"]]
    if job["state"] == "cancelled":
        return _renewal(item, "cancelled")
    if run["finished"]:
        return _renewal(item, "mismatch")
    if float(run["lease_expires"]) <= now:
        return _renewal(item, "expired")
    run["lease_expires"] = now + stand.lease_seconds
    return _renewal(item, "renewed", iso(run["lease_expires"]))


def pending_commands(state: Json, worker_id: str) -> list[Json]:
    return [
        {name: command[name] for name in COMMAND_FIELDS}
        for command in state["commands"].values()
        if command["worker_id"] == worker_id and command["ack"] is None
    ]


def handle(stand: Stand, req: Request) -> tuple[int, Json]:
    body = req.validated("HeartbeatRequest")
    if not SUPPORTED_SCHEMA_VERSIONS.intersection(body["schema_versions"]):
        raise ApiError(
            400, "schema_unsupported", f"server supports {sorted(SUPPORTED_SCHEMA_VERSIONS)}"
        )
    now, worker_id = stand.now(), req.principal
    record_worker(stand, worker_id, body, now)
    apply_acks(stand.state, worker_id, body["acknowledgements"], now)
    leases = [renew(stand, worker_id, item, now) for item in body["active_jobs"]]
    commands = pending_commands(stand.state, worker_id)
    return 200, {"server_time": iso(now), "leases": leases, "commands": commands}
