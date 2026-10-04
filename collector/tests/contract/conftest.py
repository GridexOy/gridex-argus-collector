"""Contract tests of /api/collector (TZ_SELAIN 12.4) through the generated client.

Against the local contract_server by default. Set ARGUS_CONTRACT_BASE_URL
(e.g. https://argus.gridex.fi/api/collector) with ARGUS_CONTRACT_WORKER_ID,
ARGUS_CONTRACT_WORKER_TOKEN and ARGUS_CONTRACT_SYSTEM_TOKEN to run the same
set against another implementation (block 6 runs it in its CI).
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass

import pytest

from collector.tests.contract.system import SystemClient
from contract_server import server as contract_server


@dataclass(frozen=True)
class Argus:
    base_url: str  # .../api/collector
    worker_id: str
    token: str
    system: SystemClient
    proxy: str


@pytest.fixture
def argus() -> Iterator[Argus]:
    remote = os.environ.get("ARGUS_CONTRACT_BASE_URL")
    if remote:
        worker = os.environ["ARGUS_CONTRACT_WORKER_ID"]
        token = os.environ["ARGUS_CONTRACT_WORKER_TOKEN"]
        system = SystemClient(remote, os.environ["ARGUS_CONTRACT_SYSTEM_TOKEN"])
        yield Argus(remote.rstrip("/"), worker, token, system, "system")
        return
    srv = contract_server.start(port=0)
    base = contract_server.base_url(srv) + "/api/collector"
    try:
        yield Argus(base, "worker-main-pc", "test-token-abc",
                    SystemClient(base, "system-token-xyz"), "direct")
    finally:
        srv.shutdown()
        srv.server_close()
