"""Generated dataclasses/StrEnums for the api_client module (mechanically generated).

Source: docs/ARGUS20_COLLECTOR_OPENAPI.json.
Do not edit by hand -- see api_client/README.md to regenerate.
Pure (de)serialization for these types lives in serialization.py, split out
to stay under this repo's file-size gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class CapabilitiesReleaseLevel(StrEnum):
    M1 = "M1"
    M2 = "M2"


class CommandAckStatus(StrEnum):
    APPLIED = "applied"
    ALREADY_APPLIED = "already_applied"
    FAILED = "failed"


class LeaseRenewalStatus(StrEnum):
    RENEWED = "renewed"
    EXPIRED = "expired"
    MISMATCH = "mismatch"
    CANCELLED = "cancelled"


class CommandAction(StrEnum):
    PAUSE = "pause"
    RESUME = "resume"
    CANCEL = "cancel"
    CONTINUE = "continue"


@dataclass(frozen=True)
class HeartbeatRequest:
    worker_id: str
    worker_version: str
    schema_versions: list[str]
    capabilities: Capabilities
    collecting: bool
    active_jobs: list[ActiveLease]
    outbox_pending: int
    free_job_slots: int
    browser_available: bool
    model_available: bool
    acknowledgements: list[CommandAck]


@dataclass(frozen=True)
class HeartbeatResponse:
    server_time: str
    leases: list[LeaseRenewal]
    commands: list[Command]


@dataclass(frozen=True)
class Error:
    code: str
    detail: str
    retryable: bool
    request_id: str


@dataclass(frozen=True)
class Capabilities:
    http: bool
    browser: bool
    vision: bool
    model: bool
    document_formats: list[str]
    release_level: CapabilitiesReleaseLevel


@dataclass(frozen=True)
class ActiveLease:
    job_id: str
    run_id: str
    execution_token: str
    lease_generation: int


@dataclass(frozen=True)
class CommandAck:
    command_id: str
    status: CommandAckStatus
    detail: str


@dataclass(frozen=True)
class LeaseRenewal:
    job_id: str
    run_id: str
    status: LeaseRenewalStatus
    lease_expires_at: str | None


@dataclass(frozen=True)
class Command:
    command_id: str
    job_id: str
    action: CommandAction
    state_revision: int
    policy_patch: PolicyPatch


@dataclass(frozen=True)
class PolicyPatch:
    max_active_seconds: int = 1800
    max_pages: int = 200
    max_browser_actions: int = 400
    cloud_budget_eur: float | None = None
    human_assistance: bool | None = None
    auto_continue: bool = True
    max_runs: int = 6
    max_campaign_active_seconds: int = 10800
    max_states: int = 300
    campaign_max_pages: int = 600
    campaign_max_states: int = 900
    campaign_max_browser_actions: int = 1200
    campaign_cloud_budget_eur: float = 0.0
