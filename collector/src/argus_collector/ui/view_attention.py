"""Huomio block: hidden unless a job needs the owner (renders AttentionProps only)."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from argus_collector.ui.attention_lines import AttentionProps

PAD_X = 12
PAD_Y = 4
COLOURS = {"ok": "#1a7f37", "warn": "#9a6700", "error": "#b42318", "info": "#57606a"}


class AttentionBlock:
    def __init__(
        self,
        parent: tk.Misc,
        before: tk.Widget,
        on_open: Callable[[], None],
        on_resume: Callable[[], None],
    ) -> None:
        self.before = before
        self.frame = ttk.Frame(parent)
        self.heading = ttk.Label(self.frame, text="", style="Heading.TLabel")
        self.heading.pack(anchor="w", padx=PAD_X, pady=(12, 2))
        self.lines = ttk.Frame(self.frame)
        self.lines.pack(anchor="w", fill="x", padx=PAD_X)
        row = ttk.Frame(self.frame)
        row.pack(anchor="w", padx=PAD_X, pady=PAD_Y)
        self.open_button = ttk.Button(row, text="", command=on_open)
        self.open_button.pack(side="left", padx=(0, 8))
        self.resume_button = ttk.Button(row, text="", command=on_resume)
        self.resume_button.pack(side="left")
        self.hint = ttk.Label(self.frame, text="")
        self.hint.pack(anchor="w", padx=PAD_X)
        self.line_labels: list[ttk.Label] = []
        self.visible = False

    def render(self, props: AttentionProps | None) -> None:
        if props is None:
            if self.visible:
                self.frame.pack_forget()
                self.visible = False
            return
        if not self.visible:
            self.frame.pack(fill="x", before=self.before)
            self.visible = True
        self.heading.configure(text=props.title)
        for old in self.line_labels:
            old.destroy()
        self.line_labels = []
        for line in props.lines:
            label = ttk.Label(self.lines, text=line.text, wraplength=900,
                              foreground=COLOURS.get(line.level, "#1f2328"))
            label.pack(anchor="w", pady=1)
            self.line_labels.append(label)
        self.open_button.configure(text=props.open_label)
        self.open_button.state(["!disabled"] if props.open_enabled else ["disabled"])
        self.resume_button.configure(text=props.resume_label)
        hint = props.hint
        self.hint.configure(text=hint.text if hint else "",
                            foreground=COLOURS.get(hint.level, "#57606a") if hint else "#57606a")
