"""Every test run keeps off the owner's data (0.4.8.5): install.ps1 runs the tests on
MAIN-PC, and tests (or their daemon threads after a test ended) that did not set
ARGUS_COLLECTOR_HOME wrote journal lines into the real %LOCALAPPDATA% journal. The
whole session gets its own temporary data directory; a test may still set its own."""

from __future__ import annotations

import os
import tempfile

import pytest

HOME_ENV = "ARGUS_COLLECTOR_HOME"


def pytest_configure(config: pytest.Config) -> None:
    if not os.environ.get(HOME_ENV):
        os.environ[HOME_ENV] = tempfile.mkdtemp(prefix="argus-collector-tests-")
