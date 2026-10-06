"""Which events leave in the next request (WINLOG 06.10.2026, contract 3.1.0)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from argus_collector.delivery import service

NOW = datetime(2026, 10, 6, 15, 0, tzinfo=UTC)
FRESH = NOW.isoformat()


def row(seq: int, kind: str, evidence: tuple[str, ...] = (), retry: str = "") -> service.Pending:
    return service.Pending(f"e{seq}", seq, FRESH, evidence, kind, retry)


def test_an_event_does_not_wait_for_its_snapshot() -> None:
    rows = [row(1, "contact.observed", ("ev1",)), row(2, "source.processed", ("ev1",))]
    chunk = service.batch(rows, {"ev1": "pending"})
    assert [r.seq for r in chunk] == [1, 2], "ARGUS keeps it evidence_pending"
    assert service.ready(chunk, NOW, flush=False), "the page's closing event: it leaves now"
    assert not service.ready(chunk[:1], NOW, flush=False), "half a page waits up to 2 s"
    old = [service.Pending("e1", 1, (NOW - timedelta(seconds=3)).isoformat(), (), "x", "")]
    assert service.ready(old, NOW, flush=False)


def test_a_refused_event_waits_for_its_snapshot_again() -> None:
    rows = [row(1, "contact.observed", ("ev1",), retry="evidence_missing"), row(2, "job.progress")]
    assert service.batch(rows, {"ev1": "pending"}) == []
    assert len(service.batch(rows, {"ev1": "accepted"})) == 2


def test_an_event_with_a_lost_snapshot_stops_the_batch() -> None:
    rows = [row(1, "job.progress"), row(2, "contact.observed", ("ev1",))]
    assert [r.seq for r in service.batch(rows, {"ev1": "rejected"})] == [1]


def test_the_run_end_waits_for_the_run_snapshots() -> None:
    """contact.freshness names observations ARGUS applies only when their snapshot lands."""
    rows = [row(1, "source.processed", ("ev1",)), row(2, "contact.freshness"),
            row(3, "job.finished")]
    hold = ("contact.freshness", "job.finished")
    assert [r.seq for r in service.batch(rows, {"ev1": "pending"}, hold)] == [1]
    assert len(service.batch(rows, {"ev1": "accepted"})) == 3
