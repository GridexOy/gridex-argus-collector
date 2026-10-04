"""Panel wiring: data hooks (runtime, diagnostics, browser, walk) around the view.

Worker threads never touch tkinter: they put a callable on `self.ui_queue`
and the main thread runs it from `pump()`, scheduled with `after`.
"""

from __future__ import annotations

import functools
import queue
import subprocess
import threading
import tkinter as tk
from collections.abc import Callable

from argus_collector.browser import contract as browser
from argus_collector.diagnostics import contract as diagnostics
from argus_collector.runtime import contract as runtime
from argus_collector.ui import service
from argus_collector.ui.app_connection import ConnectionController
from argus_collector.ui.app_walk import WalkController
from argus_collector.ui.repository import Messages
from argus_collector.ui.service import LEVEL_ERROR, LEVEL_INFO, LEVEL_OK, Line
from argus_collector.ui.view import PanelView

POLL_MS = 250
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class PanelApp:
    """Owns the Tk root, the diagnostics thread, the launcher process and the walk."""

    def __init__(self, root: tk.Tk, msgs: Messages, config: runtime.Config) -> None:
        self.root = root
        self.msgs = msgs
        self.config = config
        self.report: diagnostics.Report | None = None
        self.report_error: str | None = None
        self.proc: subprocess.Popen[str] | None = None
        self.ui_queue: queue.Queue[Callable[[], None]] = queue.Queue()
        self.walk = WalkController(self)
        self.connection = ConnectionController(self)
        self.view = PanelView(
            root,
            self.props(),
            self.open_browser,
            self.walk.start,
            self.walk.stop,
            self.walk.open_source,
            self.connection.test_connection,
        )

    def props(self) -> service.PanelProps:
        return service.build_props(
            self.msgs,
            runtime.current_version_status(),
            self.report,
            self.report_error,
            runtime.stop_reason(),
            self.connection.props(self.msgs),
            self.walk.walking,
        )

    def refresh(self) -> None:
        self.view.render(self.props())

    def post(self, action: Callable[[], None]) -> None:
        """Queue an action for the main thread (safe from any thread)."""
        self.ui_queue.put(action)

    def pump(self) -> None:
        """Run queued UI actions and poll the launcher; main thread only."""
        while True:
            try:
                action = self.ui_queue.get_nowait()
            except queue.Empty:
                break
            action()
        self._poll_browser()

    def schedule_pump(self) -> None:
        self.pump()
        self.root.after(POLL_MS, self.schedule_pump)

    def start_diagnostics(self) -> None:
        threading.Thread(target=self._collect, name="diagnostics", daemon=True).start()

    def _collect(self) -> None:
        try:
            self.report = diagnostics.collect(self.config.model_endpoint, self.config.model_name)
            self.report_error = None
        except diagnostics.DiagnosticsError as exc:
            self.report_error = str(exc)
        self.ui_queue.put(self.refresh)

    def test_site_url(self) -> str:
        return f"http://127.0.0.1:{self.config.test_site_port}/"

    def work_browser_running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def open_browser(self) -> None:
        """Start the detached launcher; the status line follows its stdout/exit code."""
        if self.work_browser_running():
            return
        cmd = browser.launcher_command(self.test_site_url(), self.config.test_site_port)
        try:
            self.proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                cwd=str(runtime.repo_root()),
                env=browser.launcher_env(),
                creationflags=NO_WINDOW,
            )
        except OSError as exc:
            self.view.set_browser_status(
                Line(self.msgs.t("browser.failed", error=exc), LEVEL_ERROR)
            )
            return
        self.view.set_browser_status(Line(self.msgs.t("browser.opening"), LEVEL_INFO))
        threading.Thread(target=self._read_opened, args=(self.proc,), daemon=True).start()

    def _read_opened(self, proc: subprocess.Popen[str]) -> None:
        assert proc.stdout is not None
        for raw in proc.stdout:
            if '"opened": true' in raw:
                line = Line(self.msgs.t("browser.opened", url=self.test_site_url()), LEVEL_OK)
                self.ui_queue.put(functools.partial(self.view.set_browser_status, line))
                return

    def _poll_browser(self) -> None:
        proc = self.proc
        if proc is None or proc.poll() is None:
            return
        self.proc = None
        if proc.returncode == 0:
            self.view.set_browser_status(Line(self.msgs.t("browser.closed"), LEVEL_INFO))
            return
        err = proc.stderr.read().strip() if proc.stderr else ""
        detail = err.splitlines()[-1] if err else f"exit code {proc.returncode}"
        self.view.set_browser_status(Line(self.msgs.t("browser.failed", error=detail), LEVEL_ERROR))
