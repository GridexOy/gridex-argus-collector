"""Why ARGUS refused (0.4.8.1): every rejection in the journal with its id and words."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from argus_collector.api_client import contract as api
from argus_collector.delivery import contract as delivery
from argus_collector.delivery import results
from argus_collector.delivery.hooks import Failed
from argus_collector.storage import contract as storage

TARGET = delivery.ApiTarget("http://127.0.0.1:9/api/collector", "worker-1", "token", "direct")


class Recorder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str, str]] = []

    def token_for(self, conn: sqlite3.Connection, job_id: str, run_id: str) -> str | None:
        return None

    def lease_problem(self, job_id: str, run_id: str, code: str, token: str) -> None:
        return None

    def rejected(self, conn: sqlite3.Connection, job_id: str, kind: str, code: str,
                 item: str) -> None:
        self.calls.append((job_id, kind, code, item))

    def applied(self, conn: sqlite3.Connection, job_id: str, resp: api.EventsResponse) -> None:
        return None


def journal(home: Path) -> str:
    return "".join(p.read_text("utf-8") for p in (home / "logs").glob("*.log"))


def outbox(conn: sqlite3.Connection, seq: int, status: str = "pending", code: str = "",
           at: str = "2026-10-05T10:00:00+00:00") -> str:
    event_id = f"e{seq}"
    with conn:
        conn.execute(
            "INSERT INTO outbox (event_id, job_id, run_id, seq, type, event_json,"
            " evidence_ids_json, created_at, status, code, sent_at)"
            " VALUES (?, 'j1', 'r1', ?, 'contact.observed', '{}', '[\"ev1\"]', ?, ?, ?, ?)",
            (event_id, seq, at, status, code, at if status != "pending" else None),
        )
    return event_id


def answer(*items: tuple[str, int, str, str | None]) -> api.EventsResponse:
    return api.from_json(api.EventsResponse, {
        "results": [{"event_id": e, "seq": s, "status": st, "code": c,
                     "canonical_contact_id": None, "server_revision": 1,
                     "state_applied": st == "accepted", "channel_status": None}
                    for e, s, st, c in items],
        "last_contiguous_seq": 1, "job_state": "running", "next_run_scheduled": False,
    })


@pytest.fixture
def home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("ARGUS_COLLECTOR_HOME", str(tmp_path / "home"))
    return tmp_path / "home"


def test_each_rejected_event_has_its_id_code_and_words(home: Path, tmp_path: Path) -> None:
    conn = storage.connect(tmp_path / "c.sqlite3")
    try:
        ids = [outbox(conn, seq) for seq in (1, 2, 3)]
        rows = {r["event_id"]: r for r in conn.execute("SELECT * FROM outbox")}
        hooks = Recorder()
        resp = answer((ids[0], 1, "accepted", None),
                      (ids[1], 2, "rejected", "evidence_hash_mismatch"),
                      (ids[2], 3, "rejected", "sequence_gap"))
        results.apply(conn, hooks, "j1", rows, resp)
        assert hooks.calls == [("j1", "contact.observed", "evidence_hash_mismatch",
                                "event e2 seq 2")]
        log = journal(home)
        assert "event e3 seq 3 rejected sequence_gap (a gap in seq, sent again)" in log
        assert "1 accepted/duplicate, 1 rejected" in log
        assert delivery.stats(conn).last_code == "evidence_hash_mismatch"
    finally:
        conn.close()


def test_request_errors_carry_words_and_request_id(home: Path, tmp_path: Path) -> None:
    hooks = Recorder()
    deliverer = delivery.Deliverer(tmp_path / "c.sqlite3", lambda: TARGET, hooks)
    proxy_page = api.ApiError(502, None, None, "<html>502 Bad Gateway</html>")
    with pytest.raises(Failed):
        deliverer._api_error(proxy_page, "j1", "r1", "t")
    assert deliverer.server_error == 502, "the panel shows Palvelinvirhe: 502"
    body = api.Error("invalid_input", "observations[0].quote", False, "req-7")
    code = deliverer._api_error(api.ApiError(422, body, None, ""), "j1", "r1", "t")
    assert code == "invalid_input"
    bare = deliverer._api_error(api.ApiError(422, None, None, "nope"), "j1", "r1", "t")
    assert bare == "http_422", "a 4xx without an error body keeps its status"
    log = journal(home)
    assert "job j1: HTTP 502 http_502 (server error 502)" in log
    assert "job j1: HTTP 422 invalid_input (ARGUS refused the content) request_id=req-7" in log
    assert "quote" not in log, "ARGUS's detail may quote a contact value: not journaled"
    conn = storage.connect(tmp_path / "c.sqlite3")
    try:
        deliverer.tick(conn)
    finally:
        conn.close()
    assert deliverer.server_error == 0, "a pass that gets through clears it"


def test_rejections_latest_first_with_snapshots(tmp_path: Path) -> None:
    conn = storage.connect(tmp_path / "c.sqlite3")
    try:
        outbox(conn, 1, "rejected", "field_audit_missing", "2026-10-05T10:00:00+00:00")
        with conn:
            conn.execute(
                "INSERT INTO evidence_uploads (evidence_id, job_id, run_id, local_evidence_id,"
                " metadata_json, created_at, status, code, acked_at) VALUES ('ev9', 'j1', 'r1',"
                " 'l9', ?, '2026-10-05T10:00:00+00:00', 'rejected', 'payload_too_large',"
                " '2026-10-05T10:05:00+00:00')", (json.dumps({}),),
            )
        found = delivery.rejections(conn)
        assert [(r.kind, r.item_id, r.seq, r.code) for r in found] == [
            ("evidence", "ev9", None, "payload_too_large"),
            ("contact.observed", "e1", 1, "field_audit_missing"),
        ]
        assert delivery.stats(conn).errors == 2
        assert delivery.stats(conn).last_code == "payload_too_large"
    finally:
        conn.close()


def test_reason_words() -> None:
    assert delivery.reason("participation_not_confirmed") == "participation is not confirmed"
    assert delivery.reason("http_503") == "server error 503"
    assert delivery.reason("http_404") == "HTTP 404 without a reason"
    assert delivery.reason("offline") == "no answer from ARGUS"
    assert delivery.reason("brand_new") == "brand_new", "an unknown code is shown as is"


def test_error_text_for_claim_and_reconcile_lines() -> None:
    body = api.Error("lease_expired", "quote: x@y.fi", False, "req-3")
    assert delivery.error_text(api.ApiError(409, body, None, "")) == (
        "lease_expired (the lease expired) request_id=req-3")
    assert delivery.error_text(api.ApiError(502, None, None, "<html>")) == (
        "http_502 (server error 502)")
    assert delivery.error_text(api.ApiError(0, None, None, "refused")) == (
        "offline (no answer from ARGUS)")
