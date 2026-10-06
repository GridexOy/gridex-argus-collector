"""Markdown tables of `pilot.timing` (English headers): phases, who decided, models, delivery."""

from __future__ import annotations

from collections import Counter

from argus_collector.pilot.timing import PHASES, JobTiming, decide_group

PHASE_TITLES = ("Load", "Snapshot", "Extract", "Cards", "Bind", "Record", "Next step")
RULE_READERS = ("skip", "jsonld", "rules", "cache", "none")


def _s(ms: int) -> str:
    return f"{ms / 1000:.1f}"


def _pct(part: int, whole: int) -> str:
    return f"{round(100 * part / whole)} %" if whole else "—"


def _name(job: JobTiming, names: dict[str, str]) -> str:
    """The company name, else the job id (a UUID shortened to 8 characters)."""
    short = job.job_id[:8] if len(job.job_id) == 36 else job.job_id
    return names.get(job.job_id, short)


def phases_table(jobs: list[JobTiming], names: dict[str, str]) -> list[str]:
    """Chrome starts apart from the phases: 0 when the collection's Chrome was running."""
    head = "| Company | Pages | Wall s | Chrome starts | Chrome s | " + " | ".join(PHASE_TITLES)
    out = [head + " | All model calls s |", "|---" * (6 + len(PHASES)) + "|"]
    for job in jobs:
        cells = [_s(job.phases[p]) if job.states else "—" for p in PHASES]
        out.append(f"| {_name(job, names)} | {job.pages} | {job.wall_s} | {job.chrome_starts}"
                   f" | {_s(job.chrome_ms)} | " + " | ".join(cells)
                   + f" | {_s(job.model_total_ms)} |")
    return out


def chrome_line(jobs: list[JobTiming]) -> str:
    starts, ms = sum(j.chrome_starts for j in jobs), sum(j.chrome_ms for j in jobs)
    return f"Chrome: {starts} start(s) for {len(jobs)} job(s), {_s(ms)} s."


def _decisions(job: JobTiming) -> Counter[str]:
    """Steps and card reads by who made them: rules, cache or a model by name."""
    out: Counter[str] = Counter()
    for source, n in job.decide.items():
        out[decide_group(source)] += n
    for source, n in job.reader.items():
        out["rules" if source in RULE_READERS else source] += n
    for (model, purpose), n in job.model_calls.items():
        if purpose == "walk.vision":
            out[f"model:{model}"] += n
    return out


def who_table(jobs: list[JobTiming], names: dict[str, str]) -> list[str]:
    columns = sorted({k for j in jobs for k in _decisions(j) if k.startswith("model:")})
    titles = ["Rules"] + [c.removeprefix("model:") for c in columns] + ["Cache", "Fallback"]
    out = ["| Company | Decisions | " + " | ".join(titles) + " |",
           "|---" * (2 + len(titles)) + "|"]
    for job in jobs:
        counts = _decisions(job)
        total = sum(counts.values())
        cells = [counts["rules"]] + [counts[c] for c in columns]
        cells += [counts["cache"], counts["fallback"]]
        out.append(f"| {_name(job, names)} | {total} | "
                   + " | ".join(f"{n} ({_pct(n, total)})" for n in cells) + " |")
    return out


def models_table(jobs: list[JobTiming], names: dict[str, str]) -> list[str]:
    out = ["| Company | Model | Purpose | Calls | Tokens | ms total | ms mean |",
           "|---|---|---|---|---|---|---|"]
    for job in jobs:
        for key in sorted(job.model_calls):
            calls, ms = job.model_calls[key], job.model_ms[key]
            out.append(f"| {_name(job, names)} | {key[0]} | {key[1]} | {calls} | "
                       f"{job.model_tokens[key]} | {ms} | {ms // calls if calls else 0} |")
    return out


def delivery_table(jobs: list[JobTiming], names: dict[str, str]) -> list[str]:
    out = ["| Company | Event batches | Events | Events ms | Snapshots | KB | Snapshots ms |",
           "|---|---|---|---|---|---|---|"]
    for job in jobs:
        out.append(f"| {_name(job, names)} | {job.event_batches} | {job.events} | "
                   f"{job.event_ms} | {job.uploads} | {job.upload_bytes // 1024} | "
                   f"{job.upload_ms} |")
    return out


def shares(jobs: list[JobTiming]) -> list[str]:
    """All jobs together: each phase's share of the measured time, largest first."""
    total: Counter[str] = Counter()
    for job in jobs:
        total.update(job.phases)
    whole = sum(total.values())
    if not whole:
        return ["No `timing` lines (a log older than 0.4.8.0): phases cannot be split; "
                "only the model calls and the time between pages are known."]
    titles = dict(zip(PHASES, PHASE_TITLES, strict=True))
    ranked = sorted(PHASES, key=lambda p: -total[p])
    return ["Phase shares (all jobs): " + ", ".join(
        f"{titles[p]} {_s(total[p])} s ({_pct(total[p], whole)})" for p in ranked if total[p])
        + "."]


def markdown(jobs: list[JobTiming], names: dict[str, str], source: str) -> str:
    parts = [f"# Walk timing from `{source}`", "", *shares(jobs), "", chrome_line(jobs), "",
             "## Phases, s", "", *phases_table(jobs, names), "",
             "## Who decided (next steps and card reads)", "", *who_table(jobs, names), "",
             "## Model calls", "", *models_table(jobs, names), "",
             "## Delivery", "", *delivery_table(jobs, names), ""]
    return "\n".join(parts)
