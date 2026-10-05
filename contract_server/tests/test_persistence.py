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


def as_older_stand(state_path: Path) -> None:
    """Rewrite a saved state into the per-job contact form of the previous stand."""
    saved = json.loads(state_path.read_text(encoding="utf-8"))
    index = {}
    for contact_id, contact in saved["contacts"].items():
        contact["job_id"] = contact.pop("job_ids")[0]
        for key in ("company_id", "aliases", "history", "last_seen_at", "not_seen"):
            del contact[key]
        for observation in contact["observations"].values():
            for key in ("job_id", "observed_at", "history", "last_confirmed_at", "superseded_by"):
                del observation[key]
        index[f"{contact['job_id']}\n{contact['entity_id']}"] = contact_id
    saved["contact_index"] = index
    state_path.write_text(json.dumps(saved), encoding="utf-8")


def test_older_contacts_are_upgraded_on_load(tmp_path: Path, clock: FakeClock) -> None:
    state_path = tmp_path / "state.json"
    first = start(state_path, clock)
    try:
        flow = Flow(Client(first))
        job = flow.start()
        evidence_id = flow.page(job, evidence_id="ev-1")
        phone = payloads.observation("phone", PHONE, "ev-1", observation_id="o-1")
        contact_id = flow.send(job, flow.contact(job, evidence_id, [phone]))[1]["results"][0][
            "canonical_contact_id"
        ]
    finally:
        stop(first)
    as_older_stand(state_path)
    second = start(state_path, clock)
    try:
        client, flow = Client(second), Flow(Client(second))
        view = client.get(f"/_stand/jobs/{job.job_id}/contacts")[1]
        assert [c["job_ids"] for c in view["contacts"]] == [[job.job_id]]
        assert flow.job_status(job.job_id)["counts"]["observations"] == 1
        email = payloads.observation("email", "info@example.fi", "ev-1")
        again = flow.send(job, flow.contact(job, evidence_id, [email]))[1]["results"][0]
        assert again["canonical_contact_id"] == contact_id
    finally:
        stop(second)
