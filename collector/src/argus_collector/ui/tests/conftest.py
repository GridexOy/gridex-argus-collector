"""Shared test helpers for the panel's tkinter tests."""

from __future__ import annotations

import time
import tkinter as tk

TK_CREATE_RETRIES = 3
TK_CREATE_RETRY_DELAY_S = 0.3


def make_tk_root() -> tk.Tk:
    """`tk.Tk()` with a short retry.

    On Windows, creating a fresh Tcl interpreter immediately after a previous
    one in the same process was torn down occasionally races Tcl's library
    init (`TclError: invalid command name "tcl_findLibrary"` or a missing
    tk.tcl), even though the previous root called `destroy()` cleanly. A
    short retry is cheaper and more robust than serialising every GUI test.
    """
    last: tk.TclError | None = None
    for _attempt in range(TK_CREATE_RETRIES):
        try:
            return tk.Tk()
        except tk.TclError as exc:
            last = exc
            time.sleep(TK_CREATE_RETRY_DELAY_S)
    assert last is not None
    raise last
