"""The timing report: journal lines -> phases, who decided, models, delivery."""

from __future__ import annotations

from argus_collector.pilot import contract
from argus_collector.walk import timing

J = "11111111-2222-3333-4444-555555555555"
LINES = [
    f"2026-10-05T10:00:00+00:00 browser: job {J}: page https://b.example/en-en/",
    f"2026-10-05T10:00:01+00:00 model: job {J}: walk.action qwen2.5:7b in=300 out=8 900 ms"
    " ok=True cost_eur=0",
    f"2026-10-05T10:00:02+00:00 browser: job {J}: timing https://b.example/en-en/ load=1200"
    " snapshot=40 extract=30 cards=0 bind=0 record=10 action=905 total=2185"
    " decide=model:qwen2.5:7b reader=skip",
    f"2026-10-05T10:00:03+00:00 browser: job {J}: page https://b.example/fi-fi/yhteystiedot/",
    f"2026-10-05T10:00:09+00:00 model: job {J}: walk.cards qwen2.5:14b in=2000 out=400 5800 ms"
    " ok=True cost_eur=0",
    f"2026-10-05T10:00:10+00:00 browser: job {J}: timing https://b.example/fi-fi/yhteystiedot/"
    " load=900 snapshot=50 extract=60 cards=5810 bind=120 record=30 action=2 total=6972"
    " decide=rule reader=model:qwen2.5:14b",
    f"2026-10-05T10:00:11+00:00 delivery: job {J}: 12 events sent, 12 accepted/duplicate,"
    " 0 rejected, last_contiguous_seq=23 in 140 ms",
    f"2026-10-05T10:00:11+00:00 delivery: job {J}: evidence 20480 B uploaded in 60 ms",
    "2026-10-05T10:00:12+00:00 http: collecting off",
]


def test_lines_are_summed_per_job() -> None:
    job = contract.parse_timing(LINES)[0]
    assert (job.pages, job.states, job.wall_s) == (2, 2, 11)
    assert job.phases["cards"] == 5810 and job.phases["load"] == 2100
    assert job.decide == {"model:qwen2.5:7b": 1, "rule": 1}
    assert job.model_calls[("qwen2.5:14b", "walk.cards")] == 1
    assert job.model_total_ms == 6700
    assert (job.events, job.event_ms, job.uploads, job.upload_ms) == (12, 140, 1, 60)


def test_markdown_names_the_largest_phase_and_the_shares() -> None:
    text = contract.timing_markdown(LINES, {J: "Beckhoff Automation Oy"}, "collector.log")
    assert "Phase shares (all jobs): Cards 5.8 s (63 %), Load 2.1 s (23 %)" in text
    row = "| Beckhoff Automation Oy | 4 | 2 (50 %) | 1 (25 %) | 1 (25 %) | 0 (0 %) | 0 (0 %) |"
    assert row in text


def test_an_old_log_without_timing_lines_is_still_read() -> None:
    old = [line for line in LINES if " timing " not in line]
    text = contract.timing_markdown(old, {}, "old.log")
    assert "No `timing` lines" in text and "| 11111111 | 2 | 11 |" in text


def test_the_walk_writes_the_line_the_report_reads() -> None:
    page = timing.PageTiming({"load": 5, "cards": 7}, decide="rule", cards="jsonld")
    line = "2026-10-05T10:00:00+00:00 browser: " + timing.line(J, "https://b.example/", page)
    job = contract.parse_timing([line])[0]
    assert (job.phases["load"], job.phases["cards"], job.reader["jsonld"]) == (5, 7, 1)
