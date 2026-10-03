"""tkinter view of the panel. Renders PanelProps only; no data access here."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from argus_collector.ui.service import (
    LEVEL_ERROR,
    LEVEL_INFO,
    LEVEL_OK,
    LEVEL_WARN,
    Line,
    PanelProps,
)

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
MIN_WIDTH = 640
MIN_HEIGHT = 480


def _style(root: tk.Tk) -> None:
    root.configure(background=BG)
    style = ttk.Style(root)
    style.theme_use("clam" if "clam" in style.theme_names() else style.theme_use())
    style.configure(".", background=BG, foreground=FG, font=("Segoe UI", 10))
    style.configure("Heading.TLabel", font=("Segoe UI", 11, "bold"))
    style.configure("Version.TLabel", font=("Consolas", 9))


def _colour(level: str) -> str:
    return COLOURS.get(level, FG)


class PanelView:
    """One window, light theme, blocks in the order of TZ_SELAIN section 5.1."""

    def __init__(self, root: tk.Tk, props: PanelProps, on_open_browser: Callable[[], None]) -> None:
        self.root = root
        self.buttons: dict[str, ttk.Button] = {}
        self.checks: dict[str, ttk.Checkbutton] = {}
        self.check_vars: dict[str, tk.BooleanVar] = {}
        self.resource_labels: list[ttk.Label] = []
        _style(root)
        root.title(props.title)
        root.minsize(MIN_WIDTH, MIN_HEIGHT)
        self.body = ttk.Frame(root)
        self.body.pack(fill="both", expand=True)
        self._build_connection(props)
        self._build_collecting(props)
        self._build_resources(props, on_open_browser)
        self.stop_label = ttk.Label(self.body, text="", wraplength=MIN_WIDTH - 40)
        self.stop_label.pack(anchor="w", padx=PAD_X, pady=PAD_Y)
        self.version_label = ttk.Label(root, style="Version.TLabel")
        self.version_label.pack(side="bottom", anchor="w", padx=12, pady=6)
        self.render(props)

    def _heading(self, text: str) -> None:
        ttk.Label(self.body, text=text, style="Heading.TLabel").pack(
            anchor="w", padx=12, pady=(12, 2)
        )

    def _build_connection(self, props: PanelProps) -> None:
        self._heading(props.connection_title)
        self.connection_label = ttk.Label(self.body)
        self.connection_label.pack(anchor="w", padx=PAD_X, pady=PAD_Y)

    def _build_collecting(self, props: PanelProps) -> None:
        self._heading(props.collecting_title)
        row = ttk.Frame(self.body)
        row.pack(anchor="w", padx=PAD_X, pady=PAD_Y)
        for name, label in (
            ("start", props.start_label),
            ("pause", props.pause_label),
            ("stop", props.stop_label),
        ):
            button = ttk.Button(row, text=label)
            button.pack(side="left", padx=(0, 8))
            self.buttons[name] = button
        for name, label in (
            ("autostart", props.autostart_label),
            ("auto_collect", props.auto_collect_label),
        ):
            var = tk.BooleanVar(self.root, value=False)
            check = ttk.Checkbutton(self.body, text=label, variable=var)
            self.check_vars[name] = var
            check.pack(anchor="w", padx=12, pady=1)
            self.checks[name] = check

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
        self._set_line(self.connection_label, props.connection_state)
        self.connection_label.configure(
            text=f"{props.connection_title}: {props.connection_state.text}"
        )
        state = "normal" if props.collecting_enabled else "disabled"
        for name in ("start", "pause", "stop"):
            self.buttons[name].state(["!disabled"] if state == "normal" else ["disabled"])
        for check in self.checks.values():
            check.state(["!disabled"] if state == "normal" else ["disabled"])
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

    def set_browser_status(self, line: Line) -> None:
        self._set_line(self.browser_status, line)

    def is_enabled(self, name: str) -> bool:
        return "disabled" not in self.buttons[name].state()
