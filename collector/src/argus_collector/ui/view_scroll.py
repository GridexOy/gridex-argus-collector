"""A vertically scrollable body for the panel window (blocks taller than the screen)."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

SCREEN_MARGIN = 80  # taskbar and window frame


class ScrollBody:
    """`inner` is the frame blocks are packed into; the window never exceeds the screen."""

    def __init__(self, root: tk.Tk, background: str) -> None:
        self.root = root
        outer = ttk.Frame(root)
        outer.pack(fill="both", expand=True)
        self.outer = outer
        self.canvas = tk.Canvas(outer, background=background, highlightthickness=0)
        self.bar = ttk.Scrollbar(outer, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.bar.set)
        self.bar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner = ttk.Frame(self.canvas)
        self._window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", self._on_inner)
        self.canvas.bind("<Configure>", self._on_canvas)
        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            root.bind_all(sequence, self._on_wheel, add="+")

    def _on_inner(self, _event: object) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        wanted = self.inner.winfo_reqheight()
        limit = self.root.winfo_screenheight() - SCREEN_MARGIN
        self.canvas.configure(height=min(wanted, limit), width=self.inner.winfo_reqwidth())

    def _on_canvas(self, event: tk.Event[tk.Canvas]) -> None:
        self.canvas.itemconfigure(self._window, width=event.width)

    def _on_wheel(self, event: tk.Event[tk.Misc]) -> None:
        if getattr(event, "num", 0) == 4 or getattr(event, "delta", 0) > 0:
            self.canvas.yview_scroll(-3, "units")
        else:
            self.canvas.yview_scroll(3, "units")

    def show(self, widget: tk.Widget) -> None:
        """Scroll so that `widget` (e.g. the Huomio block) is in view."""
        self.root.update_idletasks()
        total = max(1, self.inner.winfo_height())
        self.canvas.yview_moveto(max(0.0, widget.winfo_y() / total - 0.05))
