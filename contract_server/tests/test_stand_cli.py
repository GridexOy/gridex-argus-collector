"""The owner-side stand CLI (`python -m contract_server.stand`) against a live server."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from contract_server import openapi, server, stand
from contract_server.tests import payloads
from contract_server.tests.client import SYSTEM_TOKEN, WORKER_ID, Client
from contract_server.tests.flow import Flow

COMPANIES = [
    {
        "company_id": f"c{index}",
        "company_name": f"Company {index}",
        "seed_urls": [f"https://www.company{index}.fi/"],
        "approved_hosts": [f"company{index}.fi"],
        "priority_countries": ["FI"],
        "priority_languages": ["fi", "en"],
        **({"project_id": "p1"} if index == 1 else {}),
    }
    for index in (1, 2, 3)
]


def run(capsys: pytest.CaptureFixture[str], srv: server.ContractServer, *argv: str) -> Any:
    common = ["--base-url", server.base_url(srv), "--system-token", SYSTEM_TOKEN]
    code = stand.main([argv[0], *common, *argv[1:]])
    output = json.loads(capsys.readouterr().out)
    return code, output


@pytest.fixture
def companies_file(tmp_path: Path) -> str:
    path = tmp_path / "companies.json"
    path.write_text(json.dumps(COMPANIES), encoding="utf-8")
    return str(path)


def test_batch_builds_a_valid_request(companies_file: str) -> None:
    args = stand.build_parser().parse_args(["batch", "--companies", companies_file])
    body = stand.batch_request(args)
    assert openapi.check(body, "BatchCreateRequest") == []
    first = body["companies"][0]
    assert first["participation_status"] == "confirmed"
    assert first["scope"]["approved_hosts"] == [
        {"host": "company1.fi", "basis": "seed", "evidence_id": None}
    ]
    assert first["policy"] == stand.DEFAULT_POLICY
    assert (first["project_id"], body["companies"][1]["project_id"]) == ("p1", None)


def test_batch_and_rerun(
    capsys: pytest.CaptureFixture[str], srv: server.ContractServer, companies_file: str
) -> None:
    code, created = run(capsys, srv, "batch", "--companies", companies_file, "--only", "c1,c3")
    assert code == 0
    assert [job["company_id"] for job in created["jobs"]] == ["c1", "c3"]
    code, error = run(capsys, srv, "batch", "--companies", companies_file, "--only", "c1")
    assert (code, error["code"]) == (1, "invalid_input")
    code, _ = run(
        capsys,
        srv,
        "batch",
        "--companies",
        companies_file,
        "--only",
        "c1",
        "--rerun-reason",
        "freshness",
    )
    assert code == 0
    code, batch = run(capsys, srv, "batch-status", created["batch_id"])
    assert (code, len(batch["jobs"])) == (0, 2)


def test_control_reads_the_revision_first(
    capsys: pytest.CaptureFixture[str], srv: server.ContractServer, companies_file: str
) -> None:
    _, created = run(capsys, srv, "batch", "--companies", companies_file, "--only", "c2")
    job_id = created["jobs"][0]["job_id"]
    code, paused = run(capsys, srv, "control", job_id, "pause")
    assert (code, paused["state"], paused["state_revision"]) == (0, "paused", 1)
    code, resumed = run(capsys, srv, "control", job_id, "resume")
    assert (code, resumed["state"], resumed["state_revision"]) == (0, "queued", 2)
    code, error = run(capsys, srv, "control", job_id, "continue")
    assert (code, error["code"]) == (1, "invalid_input")
    code, job = run(capsys, srv, "job", job_id)
    assert (code, job["state_revision"]) == (0, 2)


def test_worker_and_contacts_views(
    capsys: pytest.CaptureFixture[str], srv: server.ContractServer
) -> None:
    job = Flow(Client(srv)).start()
    code, worker = run(capsys, srv, "worker", WORKER_ID)
    assert (code, worker["worker_id"], worker["queued_jobs"]) == (0, WORKER_ID, 0)
    code, view = run(capsys, srv, "contacts", job.job_id)
    assert (code, view["contacts"], view["rejected"]) == (0, [], [])
    code, error = run(capsys, srv, "job", "missing")
    assert (code, error["code"]) == (1, "invalid_input")


def test_company_contacts_view(
    capsys: pytest.CaptureFixture[str], srv: server.ContractServer
) -> None:
    flow = Flow(Client(srv))
    job = flow.start("c1")
    evidence_id = flow.page(job)
    name = payloads.observation("full_name", "Anna Virtanen", evidence_id)
    flow.send(job, flow.contact(job, evidence_id, [name]))
    code, view = run(capsys, srv, "company-contacts", "c1")
    assert (code, view["company_id"], view["job_ids"]) == (0, "c1", [job.job_id])
    contact = view["contacts"][0]
    assert (contact["entity_type"], contact["job_ids"], contact["not_seen"]) == (
        "person",
        [job.job_id],
        None,
    )
    assert contact["observations"][0]["history"] == []
    code, error = run(capsys, srv, "company-contacts", "nobody")
    assert (code, error["code"]) == (1, "invalid_input")


def test_unreachable_server_is_exit_code_1(capsys: pytest.CaptureFixture[str]) -> None:
    code = stand.main(["job", "x", "--base-url", "http://127.0.0.1:9", "--system-token", "t"])
    assert code == 1
    assert "error" in json.loads(capsys.readouterr().err)
