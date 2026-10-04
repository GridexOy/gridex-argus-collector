"""State and evidence survive a server restart when `state_path` is set."""

from __future__ import annotations

import json
from pathlib import Path

from contract_server import server
from contract_server.tests import payloads
from contract_server.tests.client import SYSTEM_TOKEN, Client
from contract_server.tests.conftest import TOKENS, FakeClock
from contract_server.tests.flow import Flow

PHONE = "+358 40 123 4567"


def start(state_path: Path, clock: FakeClock) -> server.ContractServer:
    return server.start(
        port=0, tokens=TOKENS, system_tokens={SYSTEM_TOKEN}, now=clock, state_path=state_path
    )


def stop(srv: server.ContractServer) -> None:
    srv.shutdown()
    srv.server_close()


def test_state_survives_a_restart(tmp_path: Path, clock: FakeClock) -> None:
    state_path = tmp_path / "stand" / "state.json"
    first = start(state_path, clock)
    try:
        flow = Flow(Client(first))
        job = flow.start()
        evidence_id = flow.page(job, evidence_id="ev-1")
        contact = flow.contact(job, evidence_id, [payloads.observation("phone", PHONE, "ev-1")])
        accepted = flow.send(job, contact)[1]["results"][0]
    finally:
        stop(first)
    saved = json.loads(state_path.read_text(encoding="utf-8"))
    assert job.job_id in saved["jobs"]
    evidence_dir = tmp_path / "stand" / "state.json.evidence"
    assert len(list(evidence_dir.iterdir())) == 2
    second = start(state_path, clock)
    try:
        client = Client(second)
        flow = Flow(client)
        status = flow.job_status(job.job_id)
        assert (status["state"], status["counts"]["persons"]) == ("leased", 1)
        assert "Anna Virtanen" in client.get("/_stand/evidence/ev-1")[1]["text"]
        again = flow.send(job, contact)[1]["results"][0]
        assert again["status"] == "duplicate"
        assert again["canonical_contact_id"] == accepted["canonical_contact_id"]
        body = flow.send(job, flow.event(job, "job.progress", payloads.progress()))[1]
        assert (body["results"][0]["status"], body["last_contiguous_seq"]) == ("accepted", 2)
        status_code, _ = flow.upload(job, b"<p>x</p>", evidence_id="ev-2")
        assert status_code == 201
    finally:
        stop(second)


def test_without_state_path_nothing_is_written(tmp_path: Path, clock: FakeClock) -> None:
    srv = server.start(port=0, tokens=TOKENS, system_tokens={SYSTEM_TOKEN}, now=clock)
    try:
        Flow(Client(srv)).start()
        assert srv.stand.state_file is None
    finally:
        stop(srv)
    assert list(tmp_path.iterdir()) == []
