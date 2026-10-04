"""Journal: channel prefixes, no query strings, 14-day retention."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from argus_collector.runtime import contract, journal


def test_lines_carry_the_lokit_channel(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ARGUS_COLLECTOR_HOME", str(tmp_path))
    contract.journal("delivery", "sent 3 events   job=j1")
    with pytest.raises(ValueError):
        contract.journal("contacts", "x")
    files = list((tmp_path / "logs").glob("collector-*.log"))
    assert len(files) == 1
    line = files[0].read_text(encoding="utf-8").strip()
    assert line.endswith(" delivery: sent 3 events job=j1")


def test_safe_url_drops_query_and_credentials() -> None:
    url = "https://user:pw@x.example:8443/people?email=a@b.c#top"
    assert contract.safe_url(url) == "https://x.example:8443/people"


def test_prune_keeps_two_weeks(tmp_path: Path) -> None:
    for day in ("2026-09-01", "2026-09-25", "2026-10-04"):
        target = tmp_path / "logs" / f"collector-{day}.log"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x\n", encoding="utf-8")
    removed = journal.prune(tmp_path, datetime(2026, 10, 4, 12, tzinfo=UTC))
    assert removed == 1
    names = sorted(p.name for p in (tmp_path / "logs").iterdir())
    assert names == ["collector-2026-09-25.log", "collector-2026-10-04.log"]
