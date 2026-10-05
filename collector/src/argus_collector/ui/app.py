"""Panel wiring: data hooks (runtime, diagnostics, browser, walk) around the view.

Worker threads never touch tkinter: they put a callable on `self.ui_queue`
and the main thread runs it from `pump()`, scheduled with `after`.
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from collections.abc import Callable

from argus_collector.api_client import contract as api
from argus_collector.diagnostics import contract as diagnostics
from argus_collector.models import contract as models
from argus_collector.runtime import contract as runtime
from argus_collector.scheduler import contract as scheduler
from argus_collector.ui import attention_lines, queue_lines, service
from argus_collector.ui.app_browser import WorkBrowserController
from argus_collector.ui.app_collect import CollectController
from argus_collector.ui.app_connection import ConnectionController
from argus_collector.ui.app_walk import WalkController
from argus_collector.ui.repository import Messages
from argus_collector.ui.route_lines import RouteHealth
from argus_collector.ui.service import Activity
from argus_collector.ui.view import Callbacks, PanelView

POLL_MS = 250
BLOCKS_EVERY = 4  # Jono, Lahetys and Huomio re-read the local SQLite once a second


class PanelApp:
    """Owns the Tk root, the diagnostics thread, the launcher process and the walk."""

    def __init__(self, root: tk.Tk, msgs: Messages, config: runtime.Config) -> None:
        self.root = root
        self.msgs = msgs
        self.config = config
        self.report: diagnostics.Report | None = None
        self.report_error: str | None = None
        self.routes: tuple[RouteHealth, ...] = ()
        self.browser = WorkBrowserController(self)
        self.ui_queue: queue.Queue[Callable[[], None]] = queue.Queue()
        self._pumps = 0
        self.walk = WalkController(self)
        self.connection = ConnectionController(self)
        self.collect = CollectController(self, self.connection.api_target)
        callbacks = Callbacks(
            self.open_browser, self.collect.start, self.local_test, self.collect.stop,
            self.walk.open_source, self.connection.pair, self.open_attention,
            self.attention_done,
        )
        self.view = PanelView(root, self.props(), callbacks)
        self.render_attention()

    def local_test(self, url: str) -> None:
        """Testaa paikallisesti: one site walk, nothing sent (not while collecting)."""
        if not self.collect.collecting:
            self.walk.start(url)

    def heartbeat_fields(self) -> scheduler.HeartbeatFields:
        return self.collect.collector.heartbeat_fields()

    def heartbeat_answered(self, response: api.HeartbeatResponse, acks: list[str]) -> None:
        self.collect.collector.apply_heartbeat(response, acks)

    def heartbeat_failed(self, status: int) -> None:
        self.collect.collector.heartbeat_failed(status)

    def connection_ok(self) -> None:
        """A heartbeat passed: the outbox may be sent (also when not collecting)."""
        self.collect.collector.deliverer.start()

    def activity(self) -> Activity:
        return Activity(
            walking=self.walk.walking, collecting=self.collect.collecting,
            connected=self.connection.connected,
        )

    def blocks(self) -> tuple[service.QueueProps, service.DeliveryProps]:
        collector = self.collect.collector
        return (queue_lines.queue_props(self.msgs, collector.queue_view()),
                queue_lines.delivery_props(self.msgs, collector.delivery_view()))

    def props(self) -> service.PanelProps:
        return service.build_props(
            self.msgs,
            runtime.current_version_status(),
            self.report,
            self.report_error,
            runtime.stop_reason(),
            self.connection.props(self.msgs),
            self.activity(),
            self.blocks(),
            self.routes,
        )

    def refresh(self) -> None:
        self.view.render(self.props())
        self.render_attention()

    def refresh_blocks(self) -> None:
        self.view.render_blocks(*self.blocks())
        self.render_attention()

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
        self.browser.poll()
        self._pumps += 1
        if self._pumps % BLOCKS_EVERY == 0:
            self.refresh_blocks()

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
        self.routes = self._routes()
        self.ui_queue.put(self.refresh)

    def _routes(self) -> tuple[RouteHealth, ...]:
        """The navigation and vision models: pulled on the local endpoint or not."""
        cfg, out = self.config, []
        for role, name in (("navigation", cfg.model_navigation), ("vision", cfg.model_vision)):
            target = models.resolve_role(cfg.model_endpoint, name)
            if target is not None:
                out.append(RouteHealth(role, name, models.health(target.endpoint, name)
                                       .model_listed))
        return tuple(out)

    def test_site_url(self) -> str:
        return f"http://127.0.0.1:{self.config.test_site_port}/"

    def work_browser_running(self) -> bool:
        return self.browser.running()

    @property
    def status_view(self) -> PanelView:
        return self.view

    def open_browser(self) -> None:
        """Resurssit: the work browser on the test site."""
        self.browser.open(self.test_site_url(), self.config.test_site_port)

    def _attention_item(self) -> scheduler.AttentionItem | None:
        items = self.collect.collector.attention_view()
        return items[0] if items else None

    def open_attention(self) -> None:
        """Huomio: the work browser on the page the owner has to pass by hand."""
        item = self._attention_item()
        if item is not None and not self.collect.collector.walking:
            self.browser.open(item.url)

    def attention_done(self) -> None:
        """Huomio: Jatka kasin tehdyn toimen jalkeen -> the job walks on."""
        item = self._attention_item()
        if item is not None:
            self.collect.collector.attention_done(item.job_id)
        self.refresh()

    def render_attention(self) -> None:
        walking = self.walk.walking or self.collect.collector.walking
        props = attention_lines.attention_props(
            self.msgs, self.collect.collector.attention_view(), walking, self.browser.running()
        )
        self.view.render_attention(props)
