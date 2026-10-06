"""Mutable state of one walk: budget, frontier, stop checks, gaps, ids."""

from __future__ import annotations

import sqlite3
import time
import uuid
from collections.abc import Callable
from concurrent.futures import Executor, Future
from dataclasses import dataclass, field
from typing import Any, TypeVar

from argus_collector.discovery import contract as discovery
from argus_collector.extraction import contract as extraction
from argus_collector.models import contract as models
from argus_collector.walk import service
from argus_collector.walk.goal import Tally
from argus_collector.walk.service import WalkEvent, WalkSettings
from argus_collector.walk.sink import FrontierLink, WalkCheckpoint, WalkGap, WalkSink
from argus_collector.walk.timing import PageTiming

T = TypeVar("T")
Emit = Callable[[WalkEvent], None]
ShouldStop = Callable[[], bool]
MAX_FRONTIER = 500
MAX_FAILURES_IN_ROW = 3
MAX_BRANCH_GAPS = 30  # unwalked relevant links reported as gaps per run
LOOP_REPEATS = 3  # repeats of a page state without progress that finish its branch
MAX_STALLED = 6  # actions in a row without a new page state that end the walk (0.4.8.6)
FRONTIER_INDEX_BASE = 10_000  # frontier links shown to the model get indexes from here


class StopRequested(Exception):
    """Raised between steps when the owner, the STOP file or the job asked to stop."""


@dataclass
class WalkState:
    settings: WalkSettings
    conn: sqlite3.Connection
    client: models.ModelClient  # person cards (14b)
    emit: Emit
    should_stop: ShouldStop
    run_id: str
    sink: WalkSink | None = None
    hosts: frozenset[str] = frozenset()
    focus: discovery.Focus | None = None
    cp: WalkCheckpoint = field(default_factory=WalkCheckpoint)
    emitted: set[str] = field(default_factory=set)
    failed_targets: set[str] = field(default_factory=set)
    failures_in_row: int = 0
    contacts: int = 0
    page_has_contacts: bool = False  # the last extracted page state had people or channels
    source_id: str | None = None
    end_reason: str = service.END_FINISHED
    timing: PageTiming = field(default_factory=PageTiming)  # the page state being handled
    nav_client: models.ModelClient | None = None  # next steps (7b); None: `client`
    vision_client: models.ModelClient | None = None  # screenshots (VL); None: no vision
    menu_cache: dict[str, tuple[str, str]] = field(default_factory=dict)  # menu -> choice
    read_cache: dict[str, list[extraction.Contact]] = field(default_factory=dict)  # text sha
    pool: Executor | None = None  # model calls that run while the next step is chosen
    progress: int = 0  # new fields recorded + new links remembered so far
    loops: dict[str, tuple[int, int]] = field(default_factory=dict)  # key -> (repeats, progress)
    finished_urls: set[str] = field(default_factory=set)  # finish_branch: no more clicks here
    current_key: str = ""  # the page state being handled
    clicked: dict[str, set[str]] = field(default_factory=dict)  # state key -> buttons pressed
    stalled: int = 0  # actions since the last new page state
    ruled_urls: set[str] = field(default_factory=set)  # rules read people: no model there
    goal: Tally = field(default_factory=Tally)  # people read so far (`goal.py`)
    _mark: float = field(default_factory=time.monotonic)

    def submit(self, fn: Callable[..., T], *args: Any, **kwargs: Any) -> Future[T]:
        """On the walk's worker pool; at once (a finished Future) without a pool."""
        if self.pool is not None:
            return self.pool.submit(fn, *args, **kwargs)
        done: Future[T] = Future()
        done.set_result(fn(*args, **kwargs))
        return done

    def seen_again(self, url: str, key: str) -> bool:
        """A page state seen before: True at the third repeat without new records or
        links (TZ_SELAIN 8.5) - a gap `no_progress` and finish_branch for this URL."""
        repeats, at = self.loops.get(key, (0, -1))
        repeats = repeats + 1 if at == self.progress else 1
        self.loops[key] = (repeats, self.progress)
        if repeats < LOOP_REPEATS or discovery.normalize_url(url) in self.finished_urls:
            return False
        self.finished_urls.add(discovery.normalize_url(url))
        self.add_gap(url, "no_progress", f"the page state repeated {repeats} times without new"
                     " records or links: finish_branch (TZ_SELAIN 8.5)", False)
        return True

    def navigator(self) -> models.ModelClient:
        """The navigation model; the card model once the navigation model failed."""
        return self.nav_client or self.client

    def navigation_failed(self) -> None:
        self.nav_client = None

    @property
    def job_mode(self) -> bool:
        return self.sink is not None

    def check_stop(self) -> None:
        if self.should_stop() or any(p.exists() for p in self.settings.stop_files):
            raise StopRequested()

    def step(self, step: str, detail: str = "", url: str = "") -> None:
        self.emit(WalkEvent(service.EVENT_STEP, url=url, step=step, detail=detail))

    def tick(self) -> None:
        """Add the time since the last tick to the run's active seconds."""
        now = time.monotonic()
        self.cp.active_seconds += max(0.0, now - self._mark)
        self._mark = now

    def budget_spent(self) -> bool:
        limits = self.settings.run_limits()
        return (
            self.cp.actions >= limits.actions
            or self.cp.active_seconds >= limits.seconds
            or len(self.cp.seen_keys) >= limits.states
        )

    def uid(self, kind: str, key: str) -> str:
        """Stable id within the job (`id_namespace`), so a resumed run reuses it."""
        space = uuid.uuid5(uuid.NAMESPACE_URL, "argus-collector:" + self.settings.id_namespace)
        return str(uuid.uuid5(space, f"{kind}:{key}"))

    def add_gap(self, url: str, reason: str, detail: str, resumable: bool) -> None:
        key = discovery.normalize_url(url)
        if any(g.state_key == key and g.reason == reason for g in self.cp.gaps):
            return
        gap = WalkGap(url, key, reason, detail[:300], resumable)
        self.cp.gaps.append(gap)
        if self.sink is not None:
            self.sink.gap(self.conn, gap)

    def gap_unwalked(self, reason: str, detail: str, resumable: bool = True) -> None:
        """A gap for each relevant link left in the frontier (TANDEM A4.3)."""
        links = sorted(self.cp.frontier.values(), key=lambda link: -link.score)
        relevant = [link for link in links
                    if discovery.strong_link(link.text, link.url, self.focus)]
        for link in relevant[:MAX_BRANCH_GAPS]:
            self.add_gap(link.url, reason, f"{detail}; linked from {link.parent_url}", resumable)

    def clear_gap(self, url: str, reason: str) -> None:
        """A gap solved later in the run (a bot check the owner passed) is no gap."""
        key = discovery.normalize_url(url)
        self.cp.gaps = [g for g in self.cp.gaps if not (g.state_key == key and g.reason == reason)]

    def walked(self) -> set[str]:
        """Pages walked plus links that only led back to one of them (a redirect)."""
        return set(self.cp.visited) | set(self.cp.redirected)

    def arrived(self, href: str, url: str) -> None:
        """A followed link that landed elsewhere on the approved hosts is walked with the
        page it led to: never followed again, whatever the redirect (a WPML redirect
        /contact-us/ -> /fi/ota-yhteytta/, Kontaktit 05.10.2026; owner 06.10.2026; the
        gold walks are unchanged, checked 06.10.2026)."""
        link, landed = discovery.normalize_url(href), discovery.normalize_url(url)
        if link == landed or link in self.cp.redirected or discovery.host_of(url) not in self.hosts:
            return
        self.cp.redirected.append(link)
        self.cp.frontier.pop(link, None)
        if landed in self.cp.visited:
            self.step(service.STEP_LOOP, f"{href} -> {url}: walked before", url)

    def remember_links(self, page_url: str, links: list[discovery.Candidate]) -> None:
        walked = self.walked()
        for cand in links:
            key = discovery.normalize_url(cand.href)
            if key in walked or key in self.cp.frontier or key in self.failed_targets:
                continue
            if len(self.cp.frontier) >= MAX_FRONTIER:
                return
            score = discovery.score_link(cand.text, cand.href, self.focus)
            self.cp.frontier[key] = FrontierLink(cand.href, cand.text, score, page_url)
            self.progress += 1

    def frontier_candidates(self) -> list[discovery.Candidate]:
        links = sorted(self.cp.frontier.values(), key=lambda link: -link.score)
        return [
            discovery.Candidate(FRONTIER_INDEX_BASE + i, "link", link.text, link.url, "")
            for i, link in enumerate(links)
        ]

    def mark_visited(self, url: str) -> None:
        key = discovery.normalize_url(url)
        if key not in self.cp.visited:
            self.cp.visited.append(key)
        self.cp.frontier.pop(key, None)

    def save_checkpoint(self) -> None:
        if self.sink is not None:
            self.sink.checkpoint(self.conn, self.cp)
