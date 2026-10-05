"""Single entry point of the `scheduler` module: the ARGUS job collector.

`Collector` claims jobs (<= 8, `free_job_slots`), walks them one at a time
with the job's seed, approved hosts, budget and country focus, streams
evidence and events through `delivery`, keeps leases alive through the
heartbeat answers, executes ARGUS commands (pause / resume / cancel /
continue) and reconciles after a restart, an outage or a lost lease
(ARGUS20_TZ_TANDEM.md pairs A2, A3; TZ_SELAIN 8.1, 8.6, 8.10, 8.14).
"""

from __future__ import annotations

from argus_collector.scheduler import service
from argus_collector.scheduler.collector import Collector
from argus_collector.scheduler.hooks import Settings
from argus_collector.scheduler.leases import HeartbeatFields
from argus_collector.scheduler.runner import WalkEnv
from argus_collector.scheduler.views import (
    AttentionItem,
    DeliveryView,
    JobFacts,
    QueueRow,
    QueueView,
    job_companies,
    job_facts,
)

__all__ = [
    "ACTIVE_STATES",
    "MAX_JOBS",
    "STAGE_BROWSER",
    "STAGE_FINALIZING",
    "STAGE_QUEUED",
    "AttentionItem",
    "Collector",
    "DeliveryView",
    "HeartbeatFields",
    "JobFacts",
    "QueueRow",
    "QueueView",
    "Settings",
    "WalkEnv",
    "job_companies",
    "job_facts",
]

MAX_JOBS = service.MAX_JOBS
ACTIVE_STATES = service.ACTIVE
STAGE_QUEUED = service.STAGE_QUEUED
STAGE_BROWSER = service.STAGE_BROWSER
STAGE_FINALIZING = service.STAGE_FINALIZING
