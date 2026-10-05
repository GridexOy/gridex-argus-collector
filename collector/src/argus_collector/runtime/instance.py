"""One panel per user data directory (owner 05.10.2026, 0.4.8.2).

Two panels on one machine meant two heartbeat clocks and two delivery threads
on the same outbox and journal. The panel holds an exclusive OS lock on
`<user_data_dir>/state/panel-lock` for its whole life (`msvcrt` on Windows,
`fcntl` elsewhere); the OS drops it when the process ends, also after a crash,
so a stale file never blocks. The file holds the owner's process id.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import IO

LOCK_NAME = "panel-lock"


def lock_path(base: Path) -> Path:
    return base / "state" / LOCK_NAME


def _lock(handle: IO[str]) -> None:
    if sys.platform == "win32":
        import msvcrt

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def acquire(base: Path) -> IO[str] | None:
    """The lock held open (keep it while the panel runs), or None: another panel has it."""
    path = lock_path(base)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(path, "a+", encoding="ascii")  # noqa: SIM115 - held for the process life
    try:
        _lock(handle)
    except OSError:
        handle.close()
        return None
    handle.seek(0)
    handle.truncate()
    handle.write(f"{os.getpid()}\n")
    handle.flush()
    return handle


def owner(base: Path) -> str:
    """Process id written by the panel that holds the lock ('?' when unreadable)."""
    try:
        return lock_path(base).read_text(encoding="ascii").strip() or "?"
    except OSError:
        return "?"
