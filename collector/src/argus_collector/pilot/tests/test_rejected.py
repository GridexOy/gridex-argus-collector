"""`pilot rejected`: what ARGUS rejected, per company, with the id ARGUS knows and words."""

from __future__ import annotations

from pathlib import Path

from argus_collector.pilot import contract as pilot
from argus_collector.storage import contract as storage


def test_rejected_table_names_company_id_code_and_words(tmp_path: Path) -> None:
    conn = storage.connect(tmp_path / "c.sqlite3")
    try:
        assert pilot.rejected_markdown(conn) == "No rejected events or snapshots.\n"
        with conn:
            conn.execute(
                "INSERT INTO jobs (job_id, batch_id, company_id, company_name, definition_json,"
                " state, stage, run_id, lease_token, lease_generation, lease_expires_at,"
                " claimed_at, updated_at) VALUES ('j1', 'b1', 'c1', 'Ellego Oy', '{}',"
                " 'running', 'browser', 'r1', 't', 1, 'x', 'x', 'x')"
            )
            conn.execute(
                "INSERT INTO outbox (event_id, job_id, run_id, seq, type, event_json,"
                " evidence_ids_json, created_at, status, code, sent_at) VALUES ('e7', 'j1',"
                " 'r1', 7, 'contact.observed', '{}', '[]', '2026-10-05T10:00:00+00:00',"
                " 'rejected', 'participation_not_confirmed', '2026-10-05T10:00:01+00:00')"
            )
        table = pilot.rejected_markdown(conn)
        assert "# Rejected by ARGUS: 1" in table
        assert ("| 2026-10-05T10:00:01 | Ellego Oy | j1 | contact.observed | e7 | 7"
                " | participation_not_confirmed | participation is not confirmed |") in table
    finally:
        conn.close()
