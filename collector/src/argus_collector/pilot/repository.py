"""Reading side of the pilot report: the local SQLite through other modules' contracts.

The pilot module has no tables of its own: jobs come from `scheduler`, sent
events and ARGUS's answers from `delivery`, snapshots from `evidence`.
"""

from __future__ import annotations

import random
import sqlite3
from typing import Any

from argus_collector.api_client import contract as api
from argus_collector.delivery import contract as delivery
from argus_collector.discovery import contract as discovery
from argus_collector.evidence import contract as evidence
from argus_collector.pilot import service
from argus_collector.scheduler import contract as scheduler

CONTACT = (api.ContactObservedEvent.type, api.ContactEnrichedEvent.type)
FINISHED = api.JobFinishedEvent.type
MODEL_CALLED = api.ModelCalledEvent.type


def company_row(conn: sqlite3.Connection, job: scheduler.JobFacts) -> service.CompanyRow:
    sent = [e for run in job.run_ids for e in delivery.run_results(conn, run)]
    finished = [e.payload for e in sent if e.type == FINISHED]
    active = wall = 0.0
    pages = actions = 0
    for payload in finished:
        a, w, p, b = service.finished_numbers(payload)
        active, wall, pages, actions = active + a, wall + w, max(pages, p), max(actions, b)
    calls, tokens, ms = service.model_numbers([e.payload for e in sent
                                               if e.type == MODEL_CALLED])
    contacts = [e for e in sent if e.type in CONTACT and e.channel_status]
    persons = [e for e in contacts if e.payload.get("entity_type") == "person"]
    return service.CompanyRow(
        job.company, job.state, job.completion_reason, active, wall, pages, actions, calls,
        tokens, ms, job.persons, job.channels,
        direct=sum(e.channel_status == service.DIRECT for e in persons), rated=len(contacts),
        strong_person=any(e.channel_status not in service.WEAK for e in persons),
    )


def phone_observations(conn: sqlite3.Connection,
                       job: scheduler.JobFacts) -> list[dict[str, Any]]:
    out = []
    for run in job.run_ids:
        for event in delivery.run_results(conn, run):
            observations = event.payload.get("observations") if event.type in CONTACT else []
            for obs in observations if isinstance(observations, list) else []:
                if isinstance(obs, dict) and obs.get("field") == "phone":
                    out.append(obs)
    return out


def check_phone(conn: sqlite3.Connection, job: scheduler.JobFacts,
                obs: dict[str, Any]) -> service.PhoneCheck:
    local = delivery.local_evidence_id(conn, str(obs.get("evidence_id", "")))
    snap = evidence.load_snapshot(conn, local) if local else None
    if snap is None:
        return service.PhoneCheck(job.company, str(obs.get("normalized_value")), "", False, False)
    host_ok = discovery.host_of(snap.final_url) in job.approved_hosts
    locator = obs.get("locator") if isinstance(obs.get("locator"), dict) else {}
    assert isinstance(locator, dict)
    html = snap.html.decode("utf-8", errors="replace")
    quote_ok = service.quote_at(snap.text, html, str(obs.get("quote", "")), locator)
    return service.PhoneCheck(job.company, str(obs.get("normalized_value")), snap.final_url,
                              host_ok, quote_ok)


def sample_phones(conn: sqlite3.Connection, jobs: list[scheduler.JobFacts], size: int,
                  seed: int) -> list[service.PhoneCheck]:
    pool = [(job, obs) for job in jobs for obs in phone_observations(conn, job)]
    chosen = random.Random(seed).sample(pool, min(size, len(pool)))
    return [check_phone(conn, job, obs) for job, obs in chosen]
