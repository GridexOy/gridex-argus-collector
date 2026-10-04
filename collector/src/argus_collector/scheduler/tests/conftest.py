"""Shared stands of the collector tests (module scope: one site, one fake model)."""

from __future__ import annotations

from collections.abc import Iterator
from http.server import ThreadingHTTPServer

import pytest

from argus_collector.scheduler.tests.stands import gold_persons
from argus_collector.walk.tests.fake_policy import RankedPolicy
from collector.tests.fake_model_server import FakeModelServer
from contract_server import server as contract_server
from test_site import server


@pytest.fixture(scope="module")
def site() -> Iterator[ThreadingHTTPServer]:
    srv = server.start(port=0)
    try:
        yield srv
    finally:
        srv.shutdown()
        srv.server_close()


@pytest.fixture(scope="module")
def model() -> Iterator[FakeModelServer]:
    fake = FakeModelServer(RankedPolicy(gold_persons())).start()
    try:
        yield fake
    finally:
        fake.stop()


@pytest.fixture
def argus() -> Iterator[contract_server.ContractServer]:
    srv = contract_server.start(port=0)
    try:
        yield srv
    finally:
        srv.shutdown()
        srv.server_close()
