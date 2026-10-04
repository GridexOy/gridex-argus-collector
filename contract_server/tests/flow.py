"""A worker's happy path in a few calls: batch -> claim -> evidence -> events."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from contract_server.tests import builders, payloads
from contract_server.tests.client import WORKER_ID, WORKER_TOKEN, Client
from contract_server.util import Json


@dataclass
class Job:
    job_id: str
    company_id: str
    lease: Json
    seq: int = 0

    @property
    def token(self) -> str:
        return str(self.lease["execution_token"])


class Flow:
    def __init__(self, client: Client) -> None:
        self.client = client

    def batch(self, *companies: Json) -> Json:
        status, body = self.client.system_post("/batches", builders.batch_body(*companies))
        assert status == 201, body
        return body

    def claim(
        self, max_jobs: int = 8, token: str = WORKER_TOKEN, worker_id: str = WORKER_ID
    ) -> list[Json]:
        status, body = self.client.post(
            "/jobs/claim", builders.claim_body(max_jobs, worker_id), token
        )
        assert status == 200, body
        jobs: list[Json] = body["jobs"]
        return jobs

    def start(self, company_id: str = "c1", **overrides: Any) -> Job:
        self.batch(builders.company(company_id, **overrides))
        claimed = self.claim(max_jobs=1)
        assert len(claimed) == 1
        return Job(claimed[0]["job"]["job_id"], company_id, claimed[0]["lease"])

    def upload(
        self, job: Job, data: bytes, evidence_id: str | None = None, **overrides: Any
    ) -> tuple[int, Json]:
        evidence_id = evidence_id or str(uuid.uuid4())
        token = overrides.pop("execution_token", None) or job.token
        meta = builders.metadata(job.lease, job.company_id, data, evidence_id, **overrides)
        return self.client.upload(job.job_id, meta, data, token)

    def page(self, job: Job, html: str = builders.PAGE, **overrides: Any) -> str:
        """Upload an HTML page; returns its evidence_id."""
        status, body = self.upload(job, html.encode("utf-8"), **overrides)
        assert status == 201, body
        return str(body["evidence_id"])

    def event(self, job: Job, kind: str, payload: Json, event_id: str | None = None) -> Json:
        job.seq += 1
        return builders.event(job.lease, job.seq, kind, payload, event_id)

    def send(self, job: Job, *events: Json, token: str | None = None) -> tuple[int, Json]:
        body = builders.events_body(token or job.token, list(events))
        return self.client.post(f"/jobs/{job.job_id}/events", body)

    def contact(self, job: Job, evidence_id: str, observations: list[Json], **kw: Any) -> Json:
        return self.event(
            job, "contact.observed", payloads.contact(evidence_id, observations, **kw)
        )

    def finish(self, job: Job, status: str = "completed", **overrides: Any) -> tuple[int, Json]:
        payload = payloads.finished(job.seq, status, **overrides)
        return self.send(job, self.event(job, "job.finished", payload))

    def job_status(self, job_id: str) -> Json:
        status, body = self.client.get(f"/jobs/{job_id}")
        assert status == 200, body
        return body
