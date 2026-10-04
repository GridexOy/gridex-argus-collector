"""Single entry point of the `walk` module: one company-site walk.

Loop (TZ_SELAIN section 8.4): load page -> snapshot -> deterministic
channels -> model parses person cards (verbatim-checked) -> model chooses
the next action from the numbered candidates (navigate link / click button /
scroll / finish) -> repeat within the budget, approved hosts only, until
finish, budget, STOP file or the stop callback.

A panel walk (no sink) keeps everything local. A job walk (ARGUS20_TZ_TANDEM
pair A2) gets the job's approved hosts, budget, focus and resume checkpoint
in `WalkSettings` and reports pages, findings, gaps, model calls and its
checkpoint to a `WalkSink` (the scheduler).
"""

from __future__ import annotations

from collections.abc import Callable

from argus_collector.walk import service
from argus_collector.walk.service import WalkEvent, WalkSettings, WalkSummary
from argus_collector.walk.sink import (
    AuditEntry,
    EntityFinding,
    FieldFinding,
    FrontierLink,
    PageFindings,
    PageSource,
    WalkCheckpoint,
    WalkGap,
    WalkLimits,
    WalkSink,
)

__all__ = [
    "DEFAULT_PAGE_BUDGET",
    "END_BUDGET",
    "END_DOMAIN",
    "END_ERROR",
    "END_FAILURES",
    "END_FINISHED",
    "END_START_FAILED",
    "END_STOPPED",
    "EVENT_CONTACT",
    "EVENT_DONE",
    "EVENT_ERROR",
    "EVENT_STOPPED",
    "AuditEntry",
    "EntityFinding",
    "FieldFinding",
    "FrontierLink",
    "PageFindings",
    "PageSource",
    "WalkCheckpoint",
    "WalkEvent",
    "WalkGap",
    "WalkLimits",
    "WalkSettings",
    "WalkSink",
    "WalkSummary",
    "run_walk",
    "validate_start_url",
]

DEFAULT_PAGE_BUDGET = service.DEFAULT_PAGE_BUDGET
END_FINISHED = service.END_FINISHED
END_BUDGET = service.END_BUDGET
END_STOPPED = service.END_STOPPED
END_ERROR = service.END_ERROR
END_DOMAIN = service.END_DOMAIN
END_START_FAILED = service.END_START_FAILED
END_FAILURES = service.END_FAILURES
EVENT_CONTACT = service.EVENT_CONTACT
EVENT_DONE = service.EVENT_DONE
EVENT_STOPPED = service.EVENT_STOPPED
EVENT_ERROR = service.EVENT_ERROR


def validate_start_url(raw: str) -> str | None:
    """`https://` is added when missing; None when the text is not a site URL."""
    return service.validate_start_url(raw)


def run_walk(
    settings: WalkSettings,
    on_event: Callable[[WalkEvent], None],
    should_stop: Callable[[], bool],
    sink: WalkSink | None = None,
) -> WalkSummary:
    """Run the walk to the end in the calling thread; never raises for walk errors.

    Every page, step, verified contact, error and the end are reported through
    `on_event`. `should_stop` is polled between steps (Pysayta, STOP file, job
    paused or cancelled, lease lost). `summary.end_reason` says why it ended.
    """
    from argus_collector.walk import runner  # noqa: PLC0415 - Playwright loads lazily

    return runner.run(settings, on_event, should_stop, sink)
