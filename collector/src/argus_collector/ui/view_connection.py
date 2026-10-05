"""tkinter widgets of the Yhteys block: Paritusavain, Yhdistä, the state lines."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from argus_collector.ui.connection_lines import ConnectionProps

COLOURS = {"ok": "#1a7f37", "warn": "#9a6700", "error": "#b42318"}
FG = "#1f2328"
MUTED = "#57606a"
PAD_X = 12
PAD_Y = 4
FIELD_WIDTH = 60


class ConnectionBlock:
    """Renders `ConnectionProps`; the key entry holds the token, so it is masked,
    never pre-filled and emptied after Yhdistä."""

    def __init__(
        self, parent: ttk.Frame, props: ConnectionProps, on_connect: Callable[[str], None]
    ) -> None:
        self.on_connect = on_connect
        self.key_var = tk.StringVar(parent)
        self._build_field(parent, props)
        self.key_error_label = ttk.Label(parent, text="", foreground=COLOURS["error"])
        self.paired_label = ttk.Label(parent, text=props.paired_text, foreground=MUTED)
        self.paired_label.pack(anchor="w", padx=PAD_X)
        self.state_label = ttk.Label(parent, text=props.state_text)
        self.state_label.pack(anchor="w", padx=PAD_X, pady=(PAD_Y, 0))
        self.heartbeat_label = ttk.Label(parent, text=props.heartbeat_text, foreground=MUTED)
        self.heartbeat_label.pack(anchor="w", padx=PAD_X)
        self.render(props)

    def _build_field(self, parent: ttk.Frame, props: ConnectionProps) -> None:
        row = ttk.Frame(parent)
        row.pack(anchor="w", fill="x", padx=PAD_X, pady=PAD_Y)
        ttk.Label(row, text=props.key_label).pack(side="left", padx=(0, 8))
        self.key_entry = ttk.Entry(row, textvariable=self.key_var, width=FIELD_WIDTH, show="*")
        self.key_entry.pack(side="left")
        self.key_entry.bind("<Return>", lambda _event: self._on_connect_clicked())
        self.connect_button = ttk.Button(
            row, text=props.connect_label, command=self._on_connect_clicked
        )
        self.connect_button.pack(side="left", padx=(8, 0))

    def _on_connect_clicked(self) -> None:
        if not self.connect_button.instate(["!disabled"]):
            return
        self.on_connect(self.key_var.get())
        self.key_var.set("")

    def render(self, props: ConnectionProps) -> None:
        level = props.state_level
        self.state_label.configure(text=props.state_text, foreground=COLOURS.get(level, FG))
        self.heartbeat_label.configure(text=props.heartbeat_text)
        self.paired_label.configure(text=props.paired_text)
        self.key_error_label.configure(text=props.key_error_text)
        if props.key_error_text:  # shown only while the last pasted key is refused
            self.key_error_label.pack(anchor="w", padx=PAD_X, before=self.paired_label)
        else:
            self.key_error_label.pack_forget()
        self.connect_button.state(["!disabled"] if props.connect_enabled else ["disabled"])
