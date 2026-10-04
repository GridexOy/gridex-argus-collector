"""Shared fixtures: a fake clock and a real contract server on an ephemeral port."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest

from contract_server import server
from contract_server.tests.client import (
    SYSTEM_TOKEN,
    WORKER2_ID,
    WORKER2_TOKEN,
    WORKER_ID,
    WORKER_TOKEN,
    Client,
)
from contract_server.tests.flow import Flow

TOKENS = {WORKER_TOKEN: WORKER_ID, WORKER2_TOKEN: WORKER2_ID}


class FakeClock:
    def __init__(self) -> None:
        self.current = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.current

    def advance(self, seconds: float) -> None:
        self.current += timedelta(seconds=seconds)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def srv(clock: FakeClock) -> Iterator[server.ContractServer]:
    running = server.start(port=0, tokens=TOKENS, system_tokens={SYSTEM_TOKEN}, now=clock)
    try:
        yield running
    finally:
        running.shutdown()
        running.server_close()


@pytest.fixture
def client(srv: server.ContractServer) -> Client:
    return Client(srv)


@pytest.fixture
def flow(client: Client) -> Flow:
    return Flow(client)
