"""contact.freshness at the end of a run (TZ_SELAIN 8.8, ARGUS20_TZ_TANDEM.md A4.1).

For every known contact of a re-run (ClaimedJob.known_contacts) one check per
field: what this job saw of it (the checkpoint's observations), the checked
scope (coverage.scope_description) and the evidence of the observation that
reconfirmed or changed it. The checks go out in events of at most 50, before
job.finished, whose freshness_summary counts them.
"""

from __future__ import annotations

import sqlite3
from collections import Counter
from datetime import UTC, datetime

from argus_collector.api_client import contract as api
from argus_collector.delivery import contract as delivery
from argus_collector.scheduler import events, history
from argus_collector.scheduler import repository as repo
from argus_collector.walk import contract as walk

CHECKS_PER_EVENT = 50
CONTACT_EVENTS = ("contact.observed", "contact.enriched")


def _evidence_of(conn: sqlite3.Connection, run_id: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for kind in CONTACT_EVENTS:
        for payload in delivery.run_events(conn, run_id, kind):
            observations = payload.get("observations")
            for obs in observations if isinstance(observations, list) else []:
                if isinstance(obs, dict):
                    out[str(obs.get("observation_id"))] = str(obs.get("evidence_id"))
    return out


def checks(
    conn: sqlite3.Connection,
    ids: tuple[str, str],
    known: list[api.KnownContact],
    checkpoint: walk.WalkCheckpoint,
    coverage: api.Coverage,
) -> list[api.FreshnessCheck]:
    """ids = (job_id, run_id); [] when the job has no known contacts."""
    index = history.KnownIndex(history.parse_known(known))
    if not index.known:
        return []
    seen = history.sights(repo.entity_types(conn, ids[0]), checkpoint.known_obs)
    scope = history.Scope(
        coverage.scope_description, coverage.frontier_status.value == "exhausted",
        datetime.now(UTC).isoformat(timespec="seconds"),
    )
    return history.freshness_checks(index, seen, scope, _evidence_of(conn, ids[1]))


def enqueue_tx(conn: sqlite3.Connection, ids: tuple[str, str],
               found: list[api.FreshnessCheck]) -> None:
    """Inside the caller's transaction, before job.finished."""
    for start in range(0, len(found), CHECKS_PER_EVENT):
        make = events.freshness(ids[0], ids[1], found[start : start + CHECKS_PER_EVENT])
        delivery.enqueue_event(conn, ids[0], ids[1], make, [])


def summary(found: list[api.FreshnessCheck]) -> api.FinishedPayloadFreshnessSummary:
    counted = Counter(check.status.value for check in found)
    return api.FinishedPayloadFreshnessSummary(
        reconfirmed=counted["reconfirmed"], changed=counted["changed"],
        not_seen_in_checked_scope=counted["not_seen_in_checked_scope"],
        not_checked=counted["not_checked"],
    )
