"""POST /jobs/{job_id}/control (SystemBearer): pause / resume / cancel / continue.

Optimistic `expected_state_revision` (409 "state revision is N"), replay of
`client_request_id` returns the stored response. Every applied action bumps
`state_revision` and queues a Command for the pinned worker (heartbeat).
`resume` works from paused (-> leased with a live lease) and from
needs_attention (-> running with a live lease); without one -> queued.
"""

from __future__ import annotations

from contract_server.context import Request, Stand
from contract_server.errors import conflict
from contract_server.state import current_run, job_or_404, lease_active
from contract_server.util import Json, caller_key, canonical_hash, new_id

ALLOWED_FROM = {
    "pause": frozenset({"queued", "leased", "running", "needs_attention"}),
    "resume": frozenset({"paused", "needs_attention"}),
    "cancel": frozenset({"queued", "leased", "running", "paused", "needs_attention"}),
    "continue": frozenset({"partial", "completed", "failed"}),
}


def transition(stand: Stand, job: Json, action: str, patch: Json) -> None:
    if action == "pause":
        job["state"] = "paused"
    elif action == "resume":
        run = current_run(stand.state, job)
        live = run is not None and lease_active(run, stand.now())
        held = "running" if job["state"] == "needs_attention" else "leased"
        job["state"] = held if live else "queued"
    elif action == "cancel":
        job["state"] = "cancelled"
        job["continuation"] = "none"
    else:
        job["policy"].update(patch)
        job["state"] = "queued"
        job["continuation"] = "none"


def queue_command(stand: Stand, job: Json, action: str, patch: Json) -> str:
    command_id = new_id()
    stand.state["commands"][command_id] = {
        "command_id": command_id,
        "job_id": job["job_id"],
        "action": action,
        "state_revision": job["state_revision"],
        "policy_patch": patch,
        "worker_id": job["worker_id"],
        "ack": None,
        "created_at": stand.now(),
    }
    return command_id


def handle(stand: Stand, req: Request) -> tuple[int, Json]:
    body = req.validated("ControlRequest")
    job = job_or_404(stand.state, req.params["job_id"])
    key = f"{caller_key(req.principal)}\n{body['client_request_id']}"
    digest = canonical_hash({"job_id": job["job_id"], "request": body})
    known = stand.state["controls"].get(key)
    if known is not None:
        if known["hash"] != digest:
            raise conflict("idempotency_conflict", "client_request_id reused with another payload")
        replay: Json = known["response"]
        return 200, replay
    if body["expected_state_revision"] != job["state_revision"]:
        raise conflict("invalid_input", f"state revision is {job['state_revision']}")
    action, patch = body["action"], dict(body.get("policy_patch") or {})
    if job["state"] not in ALLOWED_FROM[action]:
        raise conflict("invalid_input", f"cannot {action} a job in state {job['state']}")
    transition(stand, job, action, patch)
    job["state_revision"] += 1
    response = {
        "job_id": job["job_id"],
        "state": job["state"],
        "state_revision": job["state_revision"],
        "command_id": queue_command(stand, job, action, patch),
    }
    stand.state["controls"][key] = {"hash": digest, "response": response}
    return 200, response
