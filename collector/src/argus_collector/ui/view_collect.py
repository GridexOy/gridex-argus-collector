"""tkinter widgets of the Keruu block: URL field, buttons, status, contact table."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from argus_collector.ui.walk_lines import CollectProps

COLOURS = {"ok": "#1a7f37", "warn": "#9a6700", "error": "#b42318", "info": "#57606a"}
FG = "#1f2328"
COLUMN_WIDTHS = (160, 160, 120, 200, 240)
TABLE_ROWS = 8
URL_WIDTH = 60
PAD_X = 12
PAD_Y = 4


class CollectBlock:
    """Renders `CollectProps`; rows are appended live through `add_contact`."""

    def __init__(
        self,
        parent: ttk.Frame,
        props: CollectProps,
        on_start: Callable[[str], None],
        on_stop: Callable[[], None],
        on_open_source: Callable[[str], None],
    ) -> None:
        self.parent = parent
        self.on_open_source = on_open_source
        self.buttons: dict[str, ttk.Button] = {}
        self.checks: dict[str, ttk.Checkbutton] = {}
        self.check_vars: dict[str, tk.BooleanVar] = {}
        self.url_var = tk.StringVar(parent)
        self._build_url_row(props, on_start, on_stop)
        self._build_settings(props)
        self.hint_label = ttk.Label(parent, text="", foreground=COLOURS["warn"])
        self.hint_label.pack(anchor="w", padx=PAD_X)
        self.status_label = ttk.Label(parent, text=props.idle_status, wraplength=900)
        self.status_label.pack(anchor="w", padx=PAD_X, pady=(PAD_Y, 0))
        self.found_label = ttk.Label(parent, text="")
        self.found_label.pack(anchor="w", padx=PAD_X)
        self._build_table(props)
        self.render(props)

    def _build_url_row(
        self, props: CollectProps, on_start: Callable[[str], None], on_stop: Callable[[], None]
    ) -> None:
        row = ttk.Frame(self.parent)
        row.pack(anchor="w", fill="x", padx=PAD_X, pady=PAD_Y)
        self.url_label = ttk.Label(row, text=props.site_url_label)
        self.url_label.pack(side="left", padx=(0, 6))
        self.url_entry = ttk.Entry(row, textvariable=self.url_var, width=URL_WIDTH)
        self.url_entry.pack(side="left", padx=(0, 8))
        self.url_entry.bind("<Return>", lambda _e: on_start(self.url_var.get()))
        self.buttons["start"] = ttk.Button(
            row, text=props.start_label, command=lambda: on_start(self.url_var.get())
        )
        self.buttons["pause"] = ttk.Button(row, text=props.pause_label)
        self.buttons["stop"] = ttk.Button(row, text=props.stop_label, command=on_stop)
        for name in ("start", "pause", "stop"):
            self.buttons[name].pack(side="left", padx=(0, 8))

    def _build_settings(self, props: CollectProps) -> None:
        for name, label in (
            ("autostart", props.autostart_label),
            ("auto_collect", props.auto_collect_label),
        ):
            var = tk.BooleanVar(self.parent, value=False)
            check = ttk.Checkbutton(self.parent, text=label, variable=var)
            check.pack(anchor="w", padx=PAD_X, pady=1)
            check.state(["disabled"])
            self.check_vars[name] = var
            self.checks[name] = check

    def _build_table(self, props: CollectProps) -> None:
        frame = ttk.Frame(self.parent)
        frame.pack(fill="both", expand=True, padx=PAD_X, pady=PAD_Y)
        ids = [f"c{i}" for i in range(len(props.columns))]
        self.table = ttk.Treeview(frame, columns=ids, show="headings", height=TABLE_ROWS)
        for column, heading, width in zip(ids, props.columns, COLUMN_WIDTHS, strict=False):
            self.table.heading(column, text=heading)
            self.table.column(column, width=width, anchor="w")
        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=scroll.set)
        self.table.pack(side="left", fill="both", expand=True)
        scroll.pack(side="left", fill="y")
        self.table.bind("<Double-1>", self._open_selected_source)
        self.source_hint = ttk.Label(
            self.parent, text=props.open_source_hint, foreground=COLOURS["info"]
        )
        self.source_hint.pack(anchor="w", padx=PAD_X)

    def _open_selected_source(self, _event: object) -> None:
        for item in self.table.selection():
            values = self.table.item(item, "values")
            if values and values[-1]:
                self.on_open_source(str(values[-1]))

    def render(self, props: CollectProps) -> None:
        self.buttons["start"].state(["!disabled"] if props.start_enabled else ["disabled"])
        self.buttons["stop"].state(["!disabled"] if props.stop_enabled else ["disabled"])
        self.buttons["pause"].state(["disabled"])
        self.url_entry.state(["disabled"] if props.stop_enabled else ["!disabled"])
        self.hint_label.configure(text=props.hint)

    def set_status(self, text: str, level: str) -> None:
        self.status_label.configure(text=text, foreground=COLOURS.get(level, FG))

    def set_found(self, text: str) -> None:
        self.found_label.configure(text=text)

    def clear_contacts(self) -> None:
        self.table.delete(*self.table.get_children())

    def add_contact(self, row: tuple[str, str, str, str, str]) -> None:
        item = self.table.insert("", "end", values=row)
        self.table.see(item)

    def row_count(self) -> int:
        return len(self.table.get_children())

    def is_enabled(self, name: str) -> bool:
        return "disabled" not in self.buttons[name].state()
