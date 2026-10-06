"""Keruu controller for ARGUS jobs: Kaynnista / Pysayta around the scheduler.

The collector's walk events go to the same status line and table as the
local test walk; its changes (queue, delivery) refresh the Jono and Lahetys
blocks through the panel's ui_queue (no tkinter call off the main thread).
"""

from __future__ import annotations

import functools
import threading
from collections.abc import Callable
from typing import Protocol

from argus_collector.api_client import contract as api
from argus_collector.delivery import contract as delivery
from argus_collector.diagnostics import contract as diagnostics
from argus_collector.models import contract as models
from argus_collector.runtime import contract as runtime
from argus_collector.scheduler import contract as scheduler
from argus_collector.ui import walk_lines
from argus_collector.ui.repository import Messages
from argus_collector.ui.view import PanelView
from argus_collector.walk import contract as walk

CLOSE_WAIT_S = 10.0  # the panel closes: the collecting thread closes Chrome first


class WalkHost(Protocol):
    @property
    def walking(self) -> bool: ...
    def stop(self) -> None: ...
    def reset(self) -> None: ...
    def on_event(self, event: walk.WalkEvent) -> None: ...


class Host(Protocol):
    msgs: Messages
    config: runtime.Config
    view: PanelView
    report: diagnostics.Report | None

    @property
    def walk(self) -> WalkHost: ...

    def post(self, action: Callable[[], None]) -> None: ...
    def refresh(self) -> None: ...
    def refresh_blocks(self) -> None: ...
    def work_browser_running(self) -> bool: ...


def capabilities_of(report: diagnostics.Report | None) -> api.Capabilities:
    chrome = report is not None and report.states.chrome is diagnostics.ChromeState.AVAILABLE
    model = report is not None and report.states.model is not diagnostics.ModelState.NONE
    return api.Capabilities(
        http=True, browser=chrome, vision=False, model=model, document_formats=[],
        release_level=api.CapabilitiesReleaseLevel("M1"),
    )


class CollectController:
    def __init__(self, host: Host, target: Callable[[], delivery.ApiTarget | None]) -> None:
        self.host = host
        cfg = host.config
        env = scheduler.WalkEnv(
            model=models.resolve_config(cfg.model_endpoint, cfg.model_name), headless=False,
            profile_dir=None, evidence_dir=None, db_path=None, stop_files=(),
            version=runtime.current_version_status().file_version,
            navigation=models.resolve_role(cfg.model_endpoint, cfg.model_navigation),
            vision=models.resolve_role(cfg.model_endpoint, cfg.model_vision),
            stop_at_goal=cfg.walk_stop_at_goal,
        )
        settings = scheduler.Settings(env=env, stop_files=runtime.stop_files,
                                      browser_free=lambda: not host.work_browser_running())
        self._dirty = threading.Event()
        self._job_contacts, self._job_open = 0, False
        self.collector = scheduler.Collector(
            settings, target, lambda: capabilities_of(self.host.report), self._changed,
            self._walk_event,
        )

    @property
    def collecting(self) -> bool:
        return self.collector.collecting

    def _changed(self) -> None:
        """Any thread: coalesce refreshes of the panel into one main-thread action."""
        if not self._dirty.is_set():
            self._dirty.set()
            self.host.post(self._refresh)

    def _refresh(self) -> None:
        self._dirty.clear()
        self.host.refresh()

    def _walk_event(self, event: walk.WalkEvent) -> None:
        self.host.post(functools.partial(self._on_walk_event, event))

    def _on_walk_event(self, event: walk.WalkEvent) -> None:
        """Main thread: the lines of the local walk, plus the end line of each job walk."""
        if not self._job_open:  # a new company: its own table and count (Blåkläder 44/22)
            self._job_open = True
            self.host.walk.reset()
        self.host.walk.on_event(event)
        if event.kind == walk.EVENT_CONTACT:
            self._job_contacts += 1
        elif event.kind == walk.EVENT_DONE and walk_lines.goal_line(self.host.msgs, event) is None:
            text, level = walk_lines.done_line(self.host.msgs, event.page_no, self._job_contacts)
            self.host.view.collect.set_status(text, level)
        if event.kind in (walk.EVENT_DONE, walk.EVENT_STOPPED, walk.EVENT_ERROR):
            self._job_contacts, self._job_open = 0, False

    def start(self) -> None:
        """Kaynnista: claim ARGUS jobs and walk them."""
        msgs, view = self.host.msgs, self.host.view
        if self.host.walk.walking:
            return
        if self.host.work_browser_running():
            view.collect.set_status(msgs.t("collecting.browserBusy"), "error")
            return
        self.collector.start()
        self.host.refresh()

    def shutdown(self) -> None:
        """The panel closes: collecting stops and its Chrome closes before the process ends."""
        self.collector.stop(wait_s=CLOSE_WAIT_S)

    def stop(self) -> None:
        """Pysayta: stop collecting and the local test walk; the outbox keeps sending."""
        self.collector.stop()
        self.host.walk.stop()
        self.host.refresh()
