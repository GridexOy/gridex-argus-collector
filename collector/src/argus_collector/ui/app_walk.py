"""The live event feed of the Keruu block: status line, people table, `Löydetty`.

S6 step 6.1 (TZ_SELAIN v4.0 4.1, owner 10.10.2026): the panel's own test walk
(`Testaa paikallisesti`) is gone - on MAIN-PC only `Käynnistä` is ever used, and the
stands are walked by the tests. What is left is what the owner looks at while
collecting: every walk event of the running company becomes a line or a table row.
"""

from __future__ import annotations

import webbrowser
from collections.abc import Callable
from typing import Protocol

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
        self.contacts = 0
        self.pages = 0
        self.country = ""  # `Maa: FI (vaihdettu en-br → en-fi)` of the company walked now

    def reset(self) -> None:
        """An empty table and `Löydetty: 0`: once per company while collecting."""
        self.contacts, self.pages, self.country = 0, 0, ""
        self.host.view.collect.clear_contacts()
        self.host.view.collect.set_found(self.found_text())

    def found_text(self) -> str:
        """`Löydetty: N yhteystietoa`, with the country line of the walk once it has one."""
        found = self.host.msgs.t("collecting.found", n=self.contacts)
        return f"{found} · {self.country}" if self.country else found

    def on_event(self, event: walk.WalkEvent) -> None:
        """Main thread: update status line and table from one walk event."""
        msgs, view = self.host.msgs, self.host.view
        if event.kind == "page":
            self.pages = event.page_no
        if event.kind == "step" and event.step == "country":
            self.country = walk_lines.country_line(msgs, event.detail)
            view.collect.set_found(self.found_text())
        if event.kind == "contact":
            self.contacts += 1
            view.collect.add_contact(walk_lines.contact_row(event, msgs))
            view.collect.set_found(self.found_text())
            return
        line = walk_lines.walk_event_line(msgs, event)
        if line is not None:
            view.collect.set_status(*line)

    @staticmethod
    def open_source(url: str) -> None:
        webbrowser.open(url)
