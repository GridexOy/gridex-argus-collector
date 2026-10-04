"""Single entry point of the `ui` module: start the panel window."""

from __future__ import annotations

import sys
import tkinter as tk

from argus_collector.runtime import contract as runtime
from argus_collector.ui.app import PanelApp
from argus_collector.ui.repository import load_messages

__all__ = ["create_app", "run_panel"]


def create_app(root: tk.Tk) -> PanelApp:
    """Build the panel on an existing Tk root (tests use this without mainloop)."""
    return PanelApp(root, load_messages(), runtime.load_config())


def run_panel() -> int:
    """Open the one panel window and block until it is closed."""
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        print(f"panel cannot open a window: {exc}", file=sys.stderr)
        return 2
    try:
        app = create_app(root)
    except (OSError, ValueError, KeyError) as exc:
        print(f"panel cannot start: {exc}", file=sys.stderr)
        root.destroy()
        return 2
    app.start_diagnostics()
    app.connection.start_if_saved()
    app.schedule_pump()
    root.mainloop()
    return 0
