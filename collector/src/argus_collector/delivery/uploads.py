"""The snapshot lane of delivery and the error handling both lanes share.

Uploads run on their own thread (`loop.py`): ARGUS takes 3-5 s for a new
snapshot (WINLOG 06.10.2026), and events do not wait for them.
"""

from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import Callable

from argus_collector.api_client import contract as api
from argus_collector.delivery import repository as repo
from argus_collector.delivery import service
from argus_collector.delivery.hooks import ApiTarget, DeliveryHooks, Failed
from argus_collector.delivery.transport import Transport
from argus_collector.evidence import contract as evidence
from argus_collector.runtime import contract as runtime

UPLOADS_PER_TICK = 20
HTML_MIME = "text/html; charset=utf-8"
Lane = Callable[[sqlite3.Connection, ApiTarget], None]


class Lanes:
    hooks: DeliveryHooks
    transport: Transport
    server_error: int

    def _api_error(self, exc: api.ApiError, job_id: str, run_id: str, token: str) -> str:
        """Code of an error that rejects the request; raises Failed for the classes that
        stop this pass. The journal gets the words and ARGUS's request_id."""
        body = exc.error
        code = body.code if body else service.status_code(exc.status) if exc.status else ""
        kind = service.classify(exc.status, code, body.retryable if body else False)
        rid = f" request_id={body.request_id}" if body and body.request_id else ""
        runtime.journal("delivery", f"job {job_id}: HTTP {exc.status} {code or kind}"
                        f" ({service.reason(code or kind)}){rid}")
        self.transport.answered() if exc.status else self.transport.no_answer()
        self.server_error = exc.status if exc.status >= 500 else self.server_error
        if kind == service.ERROR_LEASE:
            self.hooks.lease_problem(job_id, run_id, code, token)
        if kind in (service.ERROR_PERMANENT, service.ERROR_CONFLICT):
            return code or kind
        raise Failed(kind, exc.retry_after)

    def _uploads(self, conn: sqlite3.Connection, target: ApiTarget) -> None:
        for row in repo.pending_uploads(conn, UPLOADS_PER_TICK):
            job_id, run_id, evidence_id = row["job_id"], row["run_id"], row["evidence_id"]
            token = self.hooks.token_for(conn, job_id, run_id)
            if token is None:
                continue
            snap = evidence.load_snapshot(conn, row["local_evidence_id"])
            if snap is None:
                self._reject_upload(conn, job_id, evidence_id, "evidence_missing")
                continue
            metadata = api.from_json(api.EvidenceMetadata, json.loads(row["metadata_json"]))
            started = time.monotonic()
            try:
                resp = api.upload_evidence(
                    target.base_url, target.token, job_id, token, metadata, snap.html,
                    file_content_type=HTML_MIME, proxy_mode=target.api_mode,
                )
            except api.ApiError as exc:
                code = self._api_error(exc, job_id, run_id, token)
                self._reject_upload(conn, job_id, evidence_id, code)
                continue
            self.transport.answered()
            repo.mark_upload(conn, evidence_id, resp.status.value, "")
            runtime.journal("delivery", f"job {job_id}: evidence {len(snap.html)} B uploaded"
                            f" in {service.elapsed_ms(started)} ms")

    def _reject_upload(
        self, conn: sqlite3.Connection, job_id: str, evidence_id: str, code: str
    ) -> None:
        repo.mark_upload(conn, evidence_id, "rejected", code)
        self.hooks.rejected(conn, job_id, "evidence", code, f"evidence {evidence_id}")

