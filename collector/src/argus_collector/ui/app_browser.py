"""Work browser launcher: a detached `python -m argus_collector.browser` process.

The panel opens the visible work browser (persistent profile) on the test
site (Resurssit) or on a page that needs the owner (Huomio: a bot check to
pass by hand); the status line follows the launcher's stdout and exit code.
While it is open the collector does not start a walk (one profile, one
browser).
"""

from __future__ import annotations

import functools
import subprocess
import threading
from collections.abc import Callable
from typing import Protocol

from argus_collector.browser import contract as browser
from argus_collector.runtime import contract as runtime
from argus_collector.ui.repository import Messages
from argus_collector.ui.service import LEVEL_ERROR, LEVEL_INFO, LEVEL_OK, Line

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class StatusView(Protocol):
    def set_browser_status(self, line: Line) -> None: ...


class Host(Protocol):
    msgs: Messages

    @property
    def status_view(self) -> StatusView: ...

    def post(self, action: Callable[[], None]) -> None: ...


class WorkBrowserController:
    def __init__(self, host: Host) -> None:
        self.host = host
        self.proc: subprocess.Popen[str] | None = None

    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def open(self, url: str, serve_test_site_port: int | None = None) -> None:
        """Start the launcher on `url`; nothing when it already runs."""
        if self.running():
            return
        msgs, view = self.host.msgs, self.host.status_view
        cmd = browser.launcher_command(url, serve_test_site_port)
        try:
            self.proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                encoding="utf-8", cwd=str(runtime.repo_root()), env=browser.launcher_env(),
                creationflags=NO_WINDOW,
            )
        except OSError as exc:
            view.set_browser_status(Line(msgs.t("browser.failed", error=exc), LEVEL_ERROR))
            return
        view.set_browser_status(Line(msgs.t("browser.opening"), LEVEL_INFO))
        threading.Thread(target=self._read_opened, args=(self.proc, url), daemon=True).start()

    def _read_opened(self, proc: subprocess.Popen[str], url: str) -> None:
        assert proc.stdout is not None
        for raw in proc.stdout:
            if '"opened": true' in raw:
                line = Line(self.host.msgs.t("browser.opened", url=url), LEVEL_OK)
                self.host.post(functools.partial(self.host.status_view.set_browser_status, line))
                return

    def poll(self) -> None:
        """Main thread: report the end of the launcher once."""
        proc = self.proc
        if proc is None or proc.poll() is None:
            return
        self.proc = None
        msgs, view = self.host.msgs, self.host.status_view
        if proc.returncode == 0:
            view.set_browser_status(Line(msgs.t("browser.closed"), LEVEL_INFO))
            return
        err = proc.stderr.read().strip() if proc.stderr else ""
        detail = err.splitlines()[-1] if err else f"exit code {proc.returncode}"
        view.set_browser_status(Line(msgs.t("browser.failed", error=detail), LEVEL_ERROR))
