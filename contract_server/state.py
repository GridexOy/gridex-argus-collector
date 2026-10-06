"""The stand's whole state as one JSON-serializable dict, plus small accessors.

Collections (all dicts keep insertion = creation order):
batches, batch_keys, jobs, runs, evidence, events, contacts, contact_index,
commands, workers, controls (dicts) and model_calls, sources, records,
rejected (lists). `revision` is the server revision counter of EventResult. Contacts are
company-level (`identity.py`); `contact_index` maps entity and identity keys
to canonical_contact_id.
"""

from __future__ import annotations

from contract_server.errors import not_found
from contract_server.identity import upgrade
from contract_server.util import TERMINAL_STATES, Json

LEASE_STATES = frozenset({"leased", "running"})
DICT_KEYS = (
    "batches",
    "batch_keys",
    "jobs",
    "runs",
    "evidence",
    "events",
    "contacts",
    "contact_index",
    "commands",
    "workers",
    "controls",
    "waiting",  # 0.4.24.4: contact events that arrived before their evidence (`pending.py`)
)
LIST_KEYS = ("model_calls", "sources", "records", "rejected")


def empty_state() -> Json:
    state: Json = {"revision": 0}
    state.update({key: {} for key in DICT_KEYS})
    state.update({key: [] for key in LIST_KEYS})
    return state


def complete(state: Json) -> Json:
    """Fill collections missing from a loaded state file; upgrade older contacts."""
    for key, value in empty_state().items():
        state.setdefault(key, value)
    upgrade(state)
    return state


def job_or_404(state: Json, job_id: str) -> Json:
    job = state["jobs"].get(job_id)
    if job is None:
        raise not_found(f"unknown job {job_id}")
    result: Json = job
    return result


def run_of_job(state: Json, job: Json, run_id: str) -> Json | None:
    run = state["runs"].get(run_id)
    if run is None or run["job_id"] != job["job_id"]:
        return None
    result: Json = run
    return result


def current_run(state: Json, job: Json) -> Json | None:
    run_id = job.get("current_run_id")
    return None if run_id is None else run_of_job(state, job, run_id)


def lease_active(run: Json, now: float) -> bool:
    return not run["finished"] and float(run["lease_expires"]) > now


def is_terminal(job: Json) -> bool:
    return job["state"] in TERMINAL_STATES


def claimable(job: Json, worker_id: str) -> bool:
    """Queued and unpinned or pinned to this worker (M1 pinning)."""
    return job["state"] == "queued" and job["worker_id"] in (None, worker_id)


def expire_leases(state: Json, now: float) -> bool:
    """Lazy expiry: leased/running with an expired lease -> queued (run and pin kept)."""
    changed = False
    for job in state["jobs"].values():
        if job["state"] not in LEASE_STATES:
            continue
        run = current_run(state, job)
        if run is None or not lease_active(run, now):
            job["state"] = "queued"
            changed = True
    return changed


def bump_revision(state: Json) -> int:
    state["revision"] = int(state["revision"]) + 1
    return int(state["revision"])
