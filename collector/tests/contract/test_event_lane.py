"""WINLOG 06.10.2026 (owner, 0.4.8.7): events have their own thread and do not wait for
the snapshots ARGUS takes 3-5 s each; a page's batch leaves as soon as it is written.
Contract 3.1.0 (ARGUS 0.4.24.4): the contact before its snapshot is `evidence_pending`."""

from __future__ import annotations

import sqlite3
import time
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from argus_collector.api_client import contract as api
from argus_collector.delivery import contract as delivery
from argus_collector.delivery import repository as repo
from argus_collector.evidence import contract as evidence
from argus_collector.storage import contract as storage

from collector.tests.contract.conftest import Argus
from collector.tests.contract.system import company
from collector.tests.contract.test_evidence_loop import Hooks
from collector.tests.contract.worker import HTML, TEXT, claim, now, phone_contact, sha, started

SLOW_UPLOAD_S = 2.0


def metadata(job: api.ClaimedJob, evidence_id: str) -> api.EvidenceMetadata:
    return api.EvidenceMetadata(
        evidence_id=evidence_id, job_id=job.job.job_id, run_id=job.lease.run_id,
        company_id=job.job.company_id, source_url=job.job.seed_urls[0],
        final_url=job.job.seed_urls[0], source_kind=api.EvidenceMetadataSourceKind("browser_dom"),
        mime_type="text/html", fetched_at=now(), sha256=sha(HTML),
        byte_length=len(HTML.encode("utf-8")), capture_truncated=False, redacted=False,
        extractor_version="contract-tests", canonical_text_sha256=sha(TEXT), canonical_text=TEXT,
    )


def processed(job: api.ClaimedJob, seq: int, evidence_id: str) -> api.SourceProcessedEvent:
    payload = api.SourcePayload(source_id="src-1", url=job.job.seed_urls[0], state_key="k1",
                                parent_source_id=None, status="extracted",
                                evidence_ids=[evidence_id], detail="")
    return api.SourceProcessedEvent(event_id=str(uuid.uuid4()), job_id=job.job.job_id,
                                    run_id=job.lease.run_id, seq=seq, occurred_at=now(),
                                    payload=payload)


def page(conn: sqlite3.Connection, job: api.ClaimedJob, evidence_id: str) -> None:
    """One page in the outbox as the walk writes it: snapshot queued, events, closing event."""
    events: list[Any] = [started(job, 1), phone_contact(job, 2, evidence_id),
                         processed(job, 3, evidence_id)]
    for event in events:
        ids = [] if event.type == "job.started" else [evidence_id]
        repo.insert_event(conn, (event.event_id, job.job.job_id, job.lease.run_id, event.seq),
                          event.type, api.to_json(event), ids)
    repo.insert_upload(conn, (evidence_id, job.job.job_id, job.lease.run_id, "local-1"),
                       api.to_json(metadata(job, evidence_id)))
    conn.commit()


def slow(real: Any) -> Any:
    def upload(*args: Any, **kwargs: Any) -> Any:
        time.sleep(SLOW_UPLOAD_S)  # ARGUS's 3-5 s for a new snapshot
        return real(*args, **kwargs)
    return upload


def states(db: Path) -> tuple[list[tuple[str, str]], str]:
    conn = storage.connect(db)
    try:
        rows = [(r["status"], r["code"]) for r in conn.execute("SELECT * FROM outbox ORDER BY seq")]
        upload = conn.execute("SELECT status FROM evidence_uploads").fetchone()[0]
        return rows, str(upload)
    finally:
        conn.close()


def test_events_leave_while_the_snapshot_still_uploads(
    argus: Argus, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ARGUS_COLLECTOR_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(api, "upload_evidence", slow(api.upload_evidence))
    stored = SimpleNamespace(html=HTML.encode())
    monkeypatch.setattr(evidence, "load_snapshot", lambda conn, local: stored)
    argus.system.batch([company()])
    job = claim(argus)[0]
    db = tmp_path / "c.sqlite3"
    conn = storage.connect(db)
    page(conn, job, "ev-slow")
    conn.close()
    target = delivery.ApiTarget(argus.base_url, argus.worker_id, argus.token, argus.proxy)
    deliverer = delivery.Deliverer(db, lambda: target, Hooks(job.lease.execution_token))
    begun = time.monotonic()
    deliverer.start()
    try:
        rows, upload = states(db)
        while any(status == "pending" for status, _ in rows) and time.monotonic() - begun < 5:
            time.sleep(0.05)
            rows, upload = states(db)
        sent_after = time.monotonic() - begun
        assert upload == "pending", "the snapshot is still on its way"
        assert rows == [("accepted", ""), ("waiting", "evidence_pending"), ("accepted", "")]
        assert sent_after < 1.0, f"the page's events left after {sent_after:.2f} s"
        while (upload == "pending" or any(s == "waiting" for s, _ in rows)) \
                and time.monotonic() - begun < 15:
            time.sleep(0.05)
            rows, upload = states(db)
        assert upload == "accepted"
        assert rows[1] == ("duplicate", ""), "the verdict is asked after the upload"
        conn = storage.connect(db)
        status = conn.execute("SELECT channel_status FROM outbox WHERE seq = 2").fetchone()[0]
        conn.close()
        assert status == "published_direct", "ARGUS's rating reaches the outbox (pilot)"
    finally:
        deliverer.stop()
