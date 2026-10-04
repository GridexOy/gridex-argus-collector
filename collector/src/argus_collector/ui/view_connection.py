"""tkinter widgets of the Yhteys block: address, worker_id, token, Testaa yhteys."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from argus_collector.ui.connection_lines import ConnectionProps

COLOURS = {"ok": "#1a7f37", "warn": "#9a6700", "error": "#b42318"}
FG = "#1f2328"
PAD_X = 12
PAD_Y = 4
FIELD_WIDTH = 42


class ConnectionBlock:
    """Renders `ConnectionProps`; the token entry is write-only (never pre-filled)."""

    def __init__(
        self,
        parent: ttk.Frame,
        props: ConnectionProps,
        on_test: Callable[[str, str, str], None],
    ) -> None:
        self.on_test = on_test
        self.address_var = tk.StringVar(parent, value=props.address_value)
        self.worker_id_var = tk.StringVar(parent, value=props.worker_id_value)
        self.token_var = tk.StringVar(parent)
        self._build_fields(parent, props)
        self.state_label = ttk.Label(parent, text=props.state_text)
        self.state_label.pack(anchor="w", padx=PAD_X, pady=(PAD_Y, 0))
        self.heartbeat_label = ttk.Label(parent, text=props.heartbeat_text, foreground="#57606a")
        self.heartbeat_label.pack(anchor="w", padx=PAD_X)
        self.render(props)

    def _build_fields(self, parent: ttk.Frame, props: ConnectionProps) -> None:
        grid = ttk.Frame(parent)
        grid.pack(anchor="w", fill="x", padx=PAD_X, pady=PAD_Y)
        rows = (
            (props.address_label, self.address_var, ""),
            (props.worker_id_label, self.worker_id_var, ""),
            (props.token_label, self.token_var, "*"),
        )
        for row_index, (label_text, var, show) in enumerate(rows):
            ttk.Label(grid, text=label_text).grid(row=row_index, column=0, sticky="w", padx=(0, 8))
            entry = ttk.Entry(grid, textvariable=var, width=FIELD_WIDTH, show=show)
            entry.grid(row=row_index, column=1, sticky="w", pady=1)
        self.test_button = ttk.Button(grid, text=props.test_label, command=self._on_test_clicked)
        self.test_button.grid(row=len(rows), column=1, sticky="w", pady=(PAD_Y, 0))

    def _on_test_clicked(self) -> None:
        self.on_test(self.address_var.get(), self.worker_id_var.get(), self.token_var.get())
        self.token_var.set("")

    def render(self, props: ConnectionProps) -> None:
        level = props.state_level
        self.state_label.configure(text=props.state_text, foreground=COLOURS.get(level, FG))
        self.heartbeat_label.configure(text=props.heartbeat_text)
        self.test_button.state(["!disabled"] if props.test_enabled else ["disabled"])
