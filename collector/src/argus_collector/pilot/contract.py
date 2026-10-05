"""Single entry point of the `pilot` module: the collector side of the pilot report.

`report(conn, batch_id)` reads one batch (the latest when None) from the
local SQLite; `render_markdown(report)` gives the tables for
`docs/ARGUS20_COLLECTOR_STAGE6_REPORT.md` (ARGUS20_TZ_TANDEM.md §9).
"""

from __future__ import annotations

import sqlite3

from argus_collector.pilot import render, repository
from argus_collector.pilot.service import CompanyRow, PhoneCheck, PilotReport
from argus_collector.scheduler import contract as scheduler

__all__ = ["CompanyRow", "PhoneCheck", "PilotReport", "render_markdown", "report"]


def report(conn: sqlite3.Connection, batch_id: str | None = None, sample: int = 10,
           seed: int = 5) -> PilotReport:
    jobs = scheduler.job_facts(conn, batch_id)
    rows = [repository.company_row(conn, job) for job in jobs]
    phones = repository.sample_phones(conn, jobs, sample, seed)
    return PilotReport(jobs[0].batch_id if jobs else (batch_id or ""), rows, phones)


def render_markdown(found: PilotReport) -> str:
    return render.markdown(found)
