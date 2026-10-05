"""Markdown of the pilot report (English headers; the report around it is Russian)."""

from __future__ import annotations

from argus_collector.pilot.service import PilotReport


def _minutes(seconds: float) -> str:
    return f"{seconds / 60:.1f}"


def markdown(found: PilotReport) -> str:
    lines = [
        f"Batch `{found.batch_id}`: {len(found.rows)} companies.",
        "",
        "| Company | Result | Active min | Wall min | Pages | Actions | Model calls | Tokens |"
        " Model s | Persons | Channels | published_direct |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in found.rows:
        share = f"{r.direct}/{r.rated}" if r.rated else "-"
        result = f"{r.state} ({r.reason})" if r.reason else r.state
        lines.append(
            f"| {r.company} | {result} | {_minutes(r.active_seconds)} | {_minutes(r.wall_seconds)}"
            f" | {r.pages} | {r.actions} | {r.model_calls} | {r.model_tokens}"
            f" | {r.model_ms / 1000:.0f} | {r.persons} | {r.channels} | {share} |"
        )
    met = "met" if found.threshold_met else "not met"
    lines += [
        "",
        f"Companies with a person whose channel is not inferred / stale: "
        f"{found.strong_share:.0%} (threshold 50 %: {met}).",
        f"published_direct among the collector's rated contact events: {found.direct_share:.0%}.",
        "",
        "| # | Company | Phone | Page | Host approved | Quote in snapshot |",
        "|---|---|---|---|---|---|",
    ]
    for i, p in enumerate(found.phones, 1):
        lines.append(f"| {i} | {p.company} | {p.value} | {p.url} | {'yes' if p.host_ok else 'NO'}"
                     f" | {'yes' if p.quote_ok else 'NO'} |")
    return "\n".join(lines) + "\n"
