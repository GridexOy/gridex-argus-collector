"""Asking ARGUS for jobs: one request, its journal line and the panel's claim state.

A refused or unanswered claim is not an error of the collector - it keeps the jobs it
has and says so in Jono (`Pakettia ei saatu`), which is why the state travels back
with the count.
"""

from __future__ import annotations

import sqlite3

from argus_collector.api_client import contract as api
from argus_collector.delivery import contract as delivery
from argus_collector.runtime import contract as runtime
from argus_collector.scheduler import leases, service
from argus_collector.scheduler import repository as repo


def loading_state(conn: sqlite3.Connection, current: str) -> str:
    """`loading` while nothing is running yet, so the panel can say it is asking."""
    return "loading" if not repo.jobs(conn, service.ACTIVE) else current


def claim(conn: sqlite3.Connection, target: delivery.ApiTarget, free: int,
          capabilities: api.Capabilities, proxy_mode: str) -> tuple[int, str, str]:
    """(jobs taken, claim state, claim error) of one `POST /jobs/claim`."""
    request = api.ClaimRequest(worker_id=target.worker_id, max_jobs=free,
                               capabilities=capabilities)
    try:
        resp = api.claim_jobs(target.base_url, target.token, request,
                              proxy_mode=proxy_mode,  # type: ignore[arg-type]
                              timeout_s=delivery.API_TIMEOUT_S)
    except api.ApiError as exc:
        runtime.journal("http", f"claim: HTTP {exc.status} {delivery.error_text(exc)}")
        return 0, "failed", str(exc)
    for claimed in resp.jobs:
        kind = leases.store_claimed(conn, claimed)
        runtime.journal("http", f"claim: job {claimed.job.job_id} {kind}"
                        f" run {claimed.lease.run_id} gen {claimed.lease.lease_generation}")
    return len(resp.jobs), "done", ""
