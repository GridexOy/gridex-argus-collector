"""Evidence: canonical text, spans, snapshot files and manifest rows."""

from __future__ import annotations

from pathlib import Path

from argus_collector.evidence import contract, repository
from argus_collector.storage import contract as storage


def test_canonical_text_collapses_inline_whitespace_and_blank_lines() -> None:
    raw = "  Anna \t Virtanen \r\n\r\n   Sales   Director\n\n\n040 123 4567 "
    assert contract.canonical_text(raw) == "Anna Virtanen\nSales Director\n040 123 4567"


def test_find_span_exact_and_loose() -> None:
    text = contract.canonical_text("Anna Virtanen\nSales Director\n040 123 4567")
    exact = contract.find_span(text, "Sales Director")
    assert exact is not None
    assert (exact.start, exact.end) == (14, 28)
    assert text[exact.start : exact.end] == exact.quote == "Sales Director"
    assert exact.text_sha256 == contract.sha256_text(text)
    loose = contract.find_span(text, "Anna  Virtanen Sales")
    assert loose is not None and loose.quote == "Anna Virtanen\nSales"
    assert contract.find_span(text, "Mikko") is None
    assert contract.find_span(text, "   ") is None


def test_store_snapshot_writes_files_and_manifest(tmp_path: Path) -> None:
    conn = storage.connect(tmp_path / "collector.db")
    html = "<html><body><p>Anna   Virtanen</p></body></html>"
    first = contract.store_snapshot(
        conn, "http://a.example/", "http://a.example/index", html, "Anna   Virtanen", tmp_path
    )
    assert first.evidence_id == first.html_sha256 == contract.sha256_text(html)
    assert first.html_path.read_text(encoding="utf-8") == html
    assert first.text_path.read_text(encoding="utf-8") == "Anna Virtanen"
    assert first.html_path.parent == tmp_path / first.html_sha256[:2]
    row = repository.manifest_row(conn, first.evidence_id)
    assert row is not None and row["final_url"] == "http://a.example/index"
    again = contract.store_snapshot(conn, "http://a.example/", "x", html, "Anna Virtanen", tmp_path)
    assert again.evidence_id == first.evidence_id
    count = conn.execute("SELECT COUNT(*) FROM evidence_manifest").fetchone()[0]
    assert count == 1
    assert not list(tmp_path.glob("**/*.tmp"))
