"""tkinter view of the panel. Renders PanelProps only; no data access here."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from tkinter import ttk

from argus_collector.ui.attention_lines import AttentionProps
from argus_collector.ui.queue_lines import DeliveryProps, QueueProps
from argus_collector.ui.service import (
    LEVEL_ERROR,
    LEVEL_INFO,
    LEVEL_OK,
    LEVEL_WARN,
    Line,
    PanelProps,
)
from argus_collector.ui.view_attention import AttentionBlock
from argus_collector.ui.view_collect import CollectBlock
from argus_collector.ui.view_connection import ConnectionBlock
from argus_collector.ui.view_queue import DeliveryBlock, QueueBlock
from argus_collector.ui.view_scroll import ScrollBody

BG = "#ffffff"
FG = "#1f2328"
COLOURS = {
    LEVEL_OK: "#1a7f37",
    LEVEL_WARN: "#9a6700",
    LEVEL_ERROR: "#b42318",
    LEVEL_INFO: "#57606a",
}
PAD_X = 12
PAD_Y = 4
MIN_WIDTH = 960
MIN_HEIGHT = 860


@dataclass(frozen=True)
class Callbacks:
    open_browser: Callable[[], None]
    start_collect: Callable[[], None]  # Kaynnista: ARGUS jobs
    local_test: Callable[[str], None]  # Testaa paikallisesti: one URL, nothing sent
    stop: Callable[[], None]  # Pysayta: both
    open_source: Callable[[str], None]
    connect: Callable[[str], None]  # Yhteys: Yhdista with the pasted pairing key
    open_attention: Callable[[], None]  # Huomio: work browser on the blocked page
    attention_done: Callable[[], None]  # Huomio: Jatka kasin tehdyn toimen jalkeen


def _style(root: tk.Tk) -> None:
    root.configure(background=BG)
    style = ttk.Style(root)
    style.theme_use("clam" if "clam" in style.theme_names() else style.theme_use())
    style.configure(".", background=BG, foreground=FG, font=("Segoe UI", 10))
    style.configure("Heading.TLabel", font=("Segoe UI", 11, "bold"))
    style.configure("Version.TLabel", font=("Consolas", 9))
    style.configure("Treeview", background=BG, fieldbackground=BG, foreground=FG)


def _colour(level: str) -> str:
    return COLOURS.get(level, FG)


def _blocks(props: PanelProps) -> tuple[QueueProps, DeliveryProps]:
    if props.queue is None or props.delivery is None:
        raise ValueError("the panel needs the Jono and Lahetys props")
    return props.queue, props.delivery


class PanelView:
    """One window, light theme, blocks in the order of TZ_SELAIN section 5.1."""

    def __init__(self, root: tk.Tk, props: PanelProps, on: Callbacks) -> None:
        self.root = root
        self.buttons: dict[str, ttk.Button] = {}
        self.resource_labels: list[ttk.Label] = []
        _style(root)
        root.title(props.title)
        root.minsize(MIN_WIDTH, min(MIN_HEIGHT, root.winfo_screenheight() - 80))
        self.scroll = ScrollBody(root, BG)
        self.body = self.scroll.inner
        self._build_connection(props, on.connect)
        self._heading(props.collecting_title)
        self.collect = CollectBlock(self.body, props.collect, on)
        queue, delivery = _blocks(props)
        self._heading(queue.title)
        self.queue = QueueBlock(self.body, queue)
        self._heading(delivery.title)
        self.delivery = DeliveryBlock(self.body, delivery)
        self._build_resources(props, on.open_browser)
        self.stop_label = ttk.Label(self.body, text="", wraplength=MIN_WIDTH - 40)
        self.stop_label.pack(anchor="w", padx=PAD_X, pady=PAD_Y)
        self.attention = AttentionBlock(
            self.body, self.stop_label, on.open_attention, on.attention_done
        )
        self.version_label = ttk.Label(root, style="Version.TLabel")
        self.version_label.pack(side="bottom", anchor="w", padx=12, pady=6,
                                before=self.scroll.outer)
        self.render(props)

    def _heading(self, text: str) -> None:
        ttk.Label(self.body, text=text, style="Heading.TLabel").pack(
            anchor="w", padx=12, pady=(12, 2)
        )

    def _build_connection(self, props: PanelProps, on_connect: Callable[[str], None]) -> None:
        self._heading(props.connection.title)
        self.connection = ConnectionBlock(self.body, props.connection, on_connect)

    def _build_resources(self, props: PanelProps, on_open_browser: Callable[[], None]) -> None:
        self._heading(props.resources_title)
        self.resources_frame = ttk.Frame(self.body)
        self.resources_frame.pack(anchor="w", fill="x", padx=12)
        row = ttk.Frame(self.body)
        row.pack(anchor="w", padx=PAD_X, pady=PAD_Y)
        self.buttons["open_browser"] = ttk.Button(
            row, text=props.open_browser_label, command=on_open_browser
        )
        self.buttons["open_browser"].pack(side="left", padx=(0, 8))
        self.browser_status = ttk.Label(row, text="")
        self.browser_status.pack(side="left")

    def _set_line(self, label: ttk.Label, line: Line) -> None:
        label.configure(text=line.text, foreground=_colour(line.level))

    def render(self, props: PanelProps) -> None:
        """Apply props to existing widgets (safe to call again after a refresh)."""
        self.connection.render(props.connection)
        self.collect.render(props.collect)
        if props.queue is not None and props.delivery is not None:
            self.render_blocks(props.queue, props.delivery)
        self.buttons["open_browser"].state(
            ["!disabled"] if props.open_browser_enabled else ["disabled"]
        )
        for old in self.resource_labels:
            old.destroy()
        self.resource_labels = []
        for line in props.resources:
            label = ttk.Label(self.resources_frame, text=line.text, foreground=_colour(line.level))
            label.pack(anchor="w", pady=1)
            self.resource_labels.append(label)
        if props.stop_banner is None:
            self.stop_label.configure(text="")
        else:
            self._set_line(self.stop_label, props.stop_banner)
        self._set_line(self.version_label, props.version)

    def render_blocks(self, queue: QueueProps, delivery: DeliveryProps) -> None:
        """Jono and Lahetys only (refreshed every second from the local SQLite)."""
        self.queue.render(queue)
        self.delivery.render(delivery)

    def render_attention(self, props: AttentionProps | None) -> None:
        """Huomio: shown only while a job needs the owner (scrolled into view once)."""
        appears = props is not None and not self.attention.visible
        self.attention.render(props)
        if appears:
            self.scroll.show(self.attention.frame)

    def set_browser_status(self, line: Line) -> None:
        self._set_line(self.browser_status, line)

    def is_enabled(self, name: str) -> bool:
        if name in self.buttons:
            return "disabled" not in self.buttons[name].state()
        return self.collect.is_enabled(name)
