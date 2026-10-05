"""Walk controller of the panel: Kaynnista / Pysayta and the live event feed.

The walk runs in its own thread (Playwright sync API in that thread only);
every event is handed to the main thread through the panel's ui_queue.
"""

from __future__ import annotations

import functools
import threading
import webbrowser
from collections.abc import Callable
from typing import Protocol

from argus_collector.models import contract as models
from argus_collector.runtime import contract as runtime
from argus_collector.ui import walk_lines
from argus_collector.ui.repository import Messages
from argus_collector.ui.view import PanelView
from argus_collector.walk import contract as walk


class Host(Protocol):
    """What the controller needs from PanelApp (no tkinter calls off the main thread)."""

    msgs: Messages
    config: runtime.Config
    view: PanelView

    def post(self, action: Callable[[], None]) -> None: ...
    def refresh(self) -> None: ...
    def work_browser_running(self) -> bool: ...
    def start_diagnostics(self) -> None: ...


class WalkController:
    def __init__(self, host: Host) -> None:
        self.host = host
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.contacts = 0
        self.pages = 0

    @property
    def walking(self) -> bool:
        return self.thread is not None and self.thread.is_alive()

    def settings(self, url: str) -> walk.WalkSettings:
        cfg = self.host.config
        return walk.WalkSettings(
            start_url=url,
            model=models.resolve_config(cfg.model_endpoint, cfg.model_name),
            page_budget=cfg.walk_page_budget,
            headless=False,
            stop_files=tuple(runtime.stop_files()) or (runtime.repo_root() / "STOP",),
        )

    def start(self, raw_url: str) -> None:
        msgs, view = self.host.msgs, self.host.view
        if self.walking:
            return
        url = walk.validate_start_url(raw_url)
        if url is None:
            view.collect.set_status(msgs.t("collecting.invalidUrl", url=raw_url), "error")
            return
        if self.host.work_browser_running():
            view.collect.set_status(msgs.t("collecting.browserBusy"), "error")
            return
        self.stop_event.clear()
        self.contacts, self.pages = 0, 0
        view.collect.clear_contacts()
        view.collect.set_found(msgs.t("collecting.found", n=0))
        view.collect.set_status(msgs.t("collecting.status.starting", url=url), "info")
        self.thread = threading.Thread(
            target=self._run, args=(self.settings(url),), name="walk", daemon=True
        )
        self.thread.start()
        self.host.refresh()

    def stop(self) -> None:
        self.stop_event.set()

    def _run(self, settings: walk.WalkSettings) -> None:
        summary = walk.run_walk(settings, self._on_event_threadsafe, self.stop_event.is_set)
        self.host.post(functools.partial(self._finished, summary))

    def _on_event_threadsafe(self, event: walk.WalkEvent) -> None:
        self.host.post(functools.partial(self.on_event, event))

    def on_event(self, event: walk.WalkEvent) -> None:
        """Main thread: update status line and table from one walk event."""
        msgs, view = self.host.msgs, self.host.view
        if event.kind == "page":
            self.pages = event.page_no
        if event.kind == "contact":
            self.contacts += 1
            view.collect.add_contact(walk_lines.contact_row(event))
            view.collect.set_found(msgs.t("collecting.found", n=self.contacts))
            return
        line = walk_lines.walk_event_line(msgs, event)
        if line is not None:
            view.collect.set_status(*line)

    def _finished(self, summary: walk.WalkSummary) -> None:
        ended = not summary.stopped and not summary.error
        if ended and summary.end_reason != walk.END_ATTENTION:
            text, level = walk_lines.done_line(self.host.msgs, summary.pages, summary.contacts)
            self.host.view.collect.set_status(text, level)
        self.thread = None
        self.host.refresh()
        self.host.start_diagnostics()

    @staticmethod
    def open_source(url: str) -> None:
        webbrowser.open(url)
