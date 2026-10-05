"""Single entry point of the `ui` module: start the panel window."""

from __future__ import annotations

import os
import sys
import tkinter as tk
from tkinter import messagebox

from argus_collector.runtime import contract as runtime
from argus_collector.ui.app import PanelApp
from argus_collector.ui.repository import load_messages

__all__ = ["create_app", "run_panel"]


def create_app(root: tk.Tk) -> PanelApp:
    """Build the panel on an existing Tk root (tests use this without mainloop)."""
    return PanelApp(root, load_messages(), runtime.load_config())


def run_panel() -> int:
    """Open the one panel window and block until it is closed; a second panel on the
    same machine only says that one is open (owner 05.10.2026: one heartbeat clock)."""
    lock = runtime.panel_lock()
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        print(f"panel cannot open a window: {exc}", file=sys.stderr)
        return 2
    if lock is None:
        return _already_open(root)
    try:
        app = create_app(root)
    except (OSError, ValueError, KeyError) as exc:
        print(f"panel cannot start: {exc}", file=sys.stderr)
        root.destroy()
        return 2
    runtime.journal("http", f"panel started: pid {os.getpid()}")
    app.start_diagnostics()
    app.connection.start_if_saved()
    app.schedule_pump()
    root.mainloop()
    runtime.journal("http", f"panel closed: pid {os.getpid()}")
    lock.close()
    return 0


def _already_open(root: tk.Tk) -> int:
    pid = runtime.panel_owner()
    runtime.journal("http", f"panel not started: pid {pid} has the panel open")
    root.withdraw()
    msgs = load_messages()
    messagebox.showinfo(msgs.t("app.name"), msgs.t("panel.alreadyOpen", pid=pid), parent=root)
    root.destroy()
    return 3
