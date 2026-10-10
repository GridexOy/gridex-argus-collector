"""Pure parts of the walk: settings, events, summary, actions, URL check."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from argus_collector.browser.contract import BrowserHost
from argus_collector.discovery.contract import Candidate, Focus
from argus_collector.extraction.contract import Contact
from argus_collector.models.contract import ModelConfig
from argus_collector.walk.sink import WalkCheckpoint, WalkGap, WalkLimits

DEFAULT_PAGE_BUDGET = 15
DEFAULT_ACTION_BUDGET = 60  # browser actions of a walk from the panel (Kontaktit 05.10.2026)
UNLIMITED = 10**9

EVENT_PAGE = "page"  # a page was loaded: url, page_no, budget
EVENT_STEP = "step"  # step name in `step`, detail in `detail`
EVENT_CONTACT = "contact"  # a verified contact: contact, url, evidence_id
EVENT_DONE = "done"  # walk ended normally: detail = reason
EVENT_STOPPED = "stopped"  # stopped by the owner or STOP file
EVENT_ERROR = "error"  # walk ended with an error: error

STEP_LOADING = "loading"
STEP_EXTRACTING = "extracting"
STEP_MODEL = "model"
STEP_NAVIGATE = "navigate"
STEP_CLICK = "click"
STEP_SCROLL = "scroll"
STEP_ATTENTION = "attention"  # a bot check did not clear: detail = url
STEP_CONSENT = "consent"  # a cookie banner was answered: detail = `kind: button text`
STEP_LOOP = "loop"  # a page state repeated 3 times without progress: finish_branch
STEP_GOAL = "goal"  # the goal is reached: people, channels (owner 06.10.2026)
STEP_COUNTRY = "country"  # the country's version: detail = `FI|en-br|en-fi|local`
STEP_FOREIGN = "foreign"  # K7: a page of another domain, a source only: detail = host
STEP_GOAL_PAGES = "goal_pages"  # 2 more pages read after the first people, no goal

ACTION_NAVIGATE = "navigate"
ACTION_CLICK = "click"
ACTION_SCROLL = "scroll"
ACTION_SELECT = "select"  # choose `Action.option` in a dropdown (a country list)
ACTION_FINISH = "finish"

# Why a walk ended (WalkSummary.end_reason).
END_FINISHED = "finished"  # model/fallback finished, or nothing left to open
END_BUDGET = "budget"  # pages, actions, active time or states of the run used up
END_STOPPED = "stopped"  # Pysayta, STOP file, pause/cancel, lost lease
END_ERROR = "error"  # unexpected exception
END_DOMAIN = "domain_unresolved"  # the seed landed on a host outside approved_hosts
END_START_FAILED = "start_failed"  # the start page did not load
END_FAILURES = "action_failures"  # too many failed actions in a row
END_ATTENTION = "attention"  # a bot check did not clear: the owner solves it (8.5)
END_NO_PROGRESS = "no_progress"  # MAX_STALLED actions without a new page state (0.4.8.6)
END_GOAL = "goal"  # a sales / marketing person with a channel: completed (06.10.2026)
END_GOAL_PAGES = "goal_pages"  # people read, 2 more pages without the goal: completed


@dataclass(frozen=True)
class WalkSettings:
    """`approved_hosts`/`limits`/`focus`/`resume`/`id_namespace` are set in job mode;
    a panel walk leaves them empty (hosts = seed + redirect, budget = page_budget).
    `model` reads the person cards (14b) - the only model of the walk since 6.1:
    the rules choose every step themselves (`decide.py`)."""

    start_url: str
    model: ModelConfig
    page_budget: int = DEFAULT_PAGE_BUDGET
    action_budget: int = DEFAULT_ACTION_BUDGET  # a walk from the panel (job runs: `limits`)
    headless: bool = False
    profile_dir: Path | None = None
    evidence_dir: Path | None = None
    db_path: Path | None = None
    stop_files: tuple[Path, ...] = ()
    approved_hosts: frozenset[str] | None = None
    focus: Focus | None = None
    limits: WalkLimits | None = None
    resume: WalkCheckpoint | None = None
    id_namespace: str = ""
    region_fallback: str = "FI"
    stop_at_goal: bool = True  # the goal rule (`goal.py`); off: walk until nothing is left
    browser_host: BrowserHost | None = None  # the collection's Chrome; None: own (profile)
    company_domains: frozenset[str] | None = None  # K7: people only from these; None: any

    def run_limits(self) -> WalkLimits:
        if self.limits is not None:
            return self.limits
        return WalkLimits(self.page_budget, self.action_budget, float(UNLIMITED), UNLIMITED)


@dataclass(frozen=True)
class WalkEvent:
    kind: str
    url: str = ""
    page_no: int = 0
    budget: int = 0
    step: str = ""
    detail: str = ""
    contact: Contact | None = None
    evidence_id: str = ""
    error: str = ""
    people: int = 0  # STEP_GOAL / EVENT_DONE of a goal end: people and their channels
    channels: int = 0


@dataclass(frozen=True)
class WalkSummary:
    pages: int
    contacts: int
    stopped: bool
    error: str = ""
    visited: tuple[str, ...] = field(default_factory=tuple)
    end_reason: str = END_FINISHED
    checkpoint: WalkCheckpoint = field(default_factory=WalkCheckpoint)

    @property
    def gaps(self) -> list[WalkGap]:
        return self.checkpoint.gaps


@dataclass(frozen=True)
class Action:
    kind: str
    candidate: Candidate | None = None
    option: str = ""  # ACTION_SELECT: the option label to choose
    source: str = ""  # who chose it: structure | rule | cache | model:<name> | fallback | finish


def validate_start_url(raw: str) -> str | None:
    text = raw.strip()
    if not text or any(ch.isspace() for ch in text):
        return None
    if "://" not in text:
        text = "https://" + text
    parts = urlsplit(text)
    if parts.scheme not in ("http", "https") or not parts.hostname or "." not in parts.netloc:
        if not (parts.hostname or "").startswith("127.") and parts.hostname != "localhost":
            return None
    return text
