"""One panel per machine (0.4.8.2): a second one gets no lock; a dead panel leaves none.

On Windows `venv\\Scripts\\python.exe` is a launcher that runs the interpreter as a
child process (MAIN-PC, 0.4.8.4): the pid in `panel-pid` is the one the holding process
reports itself, not `Popen.pid`, and the test ends that process, not the launcher."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from argus_collector.runtime import instance

HOLD = (
    "import os, sys, time; from pathlib import Path; from argus_collector.runtime import"
    " instance; lock = instance.acquire(Path(sys.argv[1]));"
    " print('held' if lock else 'refused', os.getpid(), flush=True); time.sleep(60)"
)


def test_second_lock_is_refused_until_the_first_is_closed(tmp_path: Path) -> None:
    first = instance.acquire(tmp_path)
    assert first is not None
    assert instance.acquire(tmp_path) is None, "a second panel in the same machine"
    assert instance.owner(tmp_path) == str(os.getpid())
    instance.release(first)
    again = instance.acquire(tmp_path)
    assert again is not None
    instance.release(again)


def test_a_panel_process_holds_the_lock_and_its_end_frees_it(tmp_path: Path) -> None:
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)}
    proc = subprocess.Popen([sys.executable, "-c", HOLD, str(tmp_path)],
                            stdout=subprocess.PIPE, text=True, env=env)
    try:
        assert proc.stdout is not None
        said, holder = proc.stdout.readline().split()
        assert said == "held"
        assert instance.acquire(tmp_path) is None
        assert instance.owner(tmp_path) == holder, "the pid the holding process wrote itself"
        os.kill(int(holder), signal.SIGTERM)  # Windows: TerminateProcess, like a crash
        proc.wait(timeout=10)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
    deadline = time.monotonic() + 10
    lock = instance.acquire(tmp_path)
    while lock is None and time.monotonic() < deadline:
        time.sleep(0.05)
        lock = instance.acquire(tmp_path)
    assert lock is not None, "a killed panel leaves no lock behind"
    instance.release(lock)
