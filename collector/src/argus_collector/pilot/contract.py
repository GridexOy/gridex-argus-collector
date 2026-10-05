"""Single entry point of the `pilot` module: the collector side of the pilot report.

`report(conn, batch_id)` reads one batch (the latest when None) from the
local SQLite; `render_markdown(report)` gives the tables for
`docs/ARGUS20_COLLECTOR_STAGE6_REPORT.md` (ARGUS20_TZ_TANDEM.md §9).
`timing_markdown(lines, names, source)` splits a collecting day's journal
into page phases, who decided, model calls and delivery (0.4.8.0).
`rejected_markdown(conn)` lists what ARGUS rejected with its words (0.4.8.1).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable

from argus_collector.delivery import contract as delivery
from argus_collector.pilot import rejected, render, repository, timing, timing_render
from argus_collector.pilot.service import CompanyRow, PhoneCheck, PilotReport
from argus_collector.pilot.timing import JobTiming
from argus_collector.scheduler import contract as scheduler

__all__ = [
    "CompanyRow",
    "JobTiming",
    "PhoneCheck",
    "PilotReport",
    "company_names",
    "parse_timing",
    "rejected_markdown",
    "render_markdown",
    "report",
    "timing_markdown",
]


def report(conn: sqlite3.Connection, batch_id: str | None = None, sample: int = 10,
           seed: int = 5) -> PilotReport:
    jobs = scheduler.job_facts(conn, batch_id)
    rows = [repository.company_row(conn, job) for job in jobs]
    phones = repository.sample_phones(conn, jobs, sample, seed)
    return PilotReport(jobs[0].batch_id if jobs else (batch_id or ""), rows, phones)


def render_markdown(found: PilotReport) -> str:
    return render.markdown(found)


def parse_timing(lines: Iterable[str]) -> list[JobTiming]:
    return timing.parse(lines)


def company_names(conn: sqlite3.Connection) -> dict[str, str]:
    return scheduler.job_companies(conn)


def timing_markdown(lines: Iterable[str], names: dict[str, str], source: str) -> str:
    return timing_render.markdown(timing.parse(lines), names, source)


def rejected_markdown(conn: sqlite3.Connection) -> str:
    return rejected.markdown(delivery.rejections(conn), scheduler.job_companies(conn))
