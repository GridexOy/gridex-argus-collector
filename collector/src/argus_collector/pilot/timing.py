"""Where the time of a collecting day went: the collector journal, summed per job.

Pure parsing of `logs/collector-<date>.log` lines (`<ISO time> <channel>: <message>`):
`browser: job <id>: timing` (one line per page state, 0.4.8.0: phases in
ms, who decided the next step, who read the cards), `browser: job <id>: chrome
start=<ms> ms shared=yes|no` (0.4.8.6: the browser start of a walk, 0 when the
collection's Chrome was running), `model:` (every model call: purpose, model,
ms), `browser: job <id>: page` (pages; with logs older than 0.4.8.0 the time
between pages is all there is), `delivery:` (events and evidence uploads,
ms since 0.4.8.0). Nothing here reads the network or the database.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime

LINE_RE = re.compile(r"^(\S+) (\w+): (.*)$")
JOB_RE = re.compile(r"^job (\S+): (.*)$")
MODEL_RE = re.compile(r"^(\S+) (\S+) in=(\d+) out=(\d+) (\d+) ms ok=(\w+)")
PAIR_RE = re.compile(r"(\w+)=(\S+)")
EVENTS_RE = re.compile(r"^(\d+) events sent.*?(?: in (\d+) ms)?$")
UPLOAD_RE = re.compile(r"^evidence (\d+) B uploaded in (\d+) ms")
CHROME_RE = re.compile(r"^chrome start=(\d+) ms")
PHASES = ("load", "snapshot", "extract", "cards", "bind", "record", "action")


@dataclass
class JobTiming:
    job_id: str
    first: datetime | None = None
    last: datetime | None = None
    pages: int = 0  # `browser: page` lines (new page states with a snapshot)
    states: int = 0  # `timing:` lines (handled page states)
    phases: Counter[str] = field(default_factory=Counter)  # ms per phase
    decide: Counter[str] = field(default_factory=Counter)  # who chose the next step
    reader: Counter[str] = field(default_factory=Counter)  # who read the person cards
    model_calls: Counter[tuple[str, str]] = field(default_factory=Counter)  # (model, purpose)
    model_ms: Counter[tuple[str, str]] = field(default_factory=Counter)
    model_tokens: Counter[tuple[str, str]] = field(default_factory=Counter)
    events: int = 0
    event_batches: int = 0
    event_ms: int = 0
    uploads: int = 0
    upload_bytes: int = 0
    upload_ms: int = 0
    chrome_starts: int = 0  # browser starts (a walk in the running Chrome adds none)
    chrome_ms: int = 0

    def seen(self, moment: datetime) -> None:
        self.first = moment if self.first is None else min(self.first, moment)
        self.last = moment if self.last is None else max(self.last, moment)

    @property
    def wall_s(self) -> int:
        return int((self.last - self.first).total_seconds()) if self.first and self.last else 0

    @property
    def model_total_ms(self) -> int:
        return sum(self.model_ms.values())


def purpose_of(local: str) -> str:
    return local.split(":", 1)[0]


def _timing(job: JobTiming, rest: str) -> None:
    values = dict(PAIR_RE.findall(rest))
    job.states += 1
    for phase in PHASES:
        if values.get(phase, "").isdigit():
            job.phases[phase] += int(values[phase])
    job.decide[values.get("decide", "none")] += 1
    job.reader[values.get("reader", "none")] += 1


def _model(job: JobTiming, rest: str) -> None:
    found = MODEL_RE.match(rest)
    if found is None:
        return
    purpose, model = purpose_of(found.group(1)), found.group(2)
    key = (model, purpose)
    job.model_calls[key] += 1
    job.model_ms[key] += int(found.group(5))
    job.model_tokens[key] += int(found.group(3)) + int(found.group(4))


def _delivery(job: JobTiming, rest: str) -> None:
    events = EVENTS_RE.match(rest)
    if events is not None:
        job.events += int(events.group(1))
        job.event_batches += 1
        job.event_ms += int(events.group(2) or 0)
    upload = UPLOAD_RE.match(rest)
    if upload is not None:
        job.uploads += 1
        job.upload_bytes += int(upload.group(1))
        job.upload_ms += int(upload.group(2))


def _one(jobs: dict[str, JobTiming], line: str) -> None:
    parsed = LINE_RE.match(line.strip())
    if parsed is None:
        return
    stamp, channel, message = parsed.groups()
    job_line = JOB_RE.match(message)
    if job_line is None:
        return
    job_id, rest = job_line.groups()
    try:
        moment = datetime.fromisoformat(stamp)
    except ValueError:
        return
    job = jobs.setdefault(job_id, JobTiming(job_id))
    job.seen(moment)
    if channel == "browser" and rest.startswith("timing "):
        _timing(job, rest)
    elif channel == "model":
        _model(job, rest)
    elif channel == "browser" and rest.startswith("page "):
        job.pages += 1
    elif channel == "browser" and (chrome := CHROME_RE.match(rest)) and int(chrome.group(1)):
        job.chrome_starts += 1
        job.chrome_ms += int(chrome.group(1))
    elif channel == "delivery":
        _delivery(job, rest)


def parse(lines: Iterable[str]) -> list[JobTiming]:
    """One JobTiming per job id in the order the jobs first appear."""
    jobs: dict[str, JobTiming] = {}
    for line in lines:
        _one(jobs, line)
    return [j for j in jobs.values() if j.pages or j.states or j.model_calls]


def decide_group(source: str) -> str:
    """rules | cache | model:<name> | fallback for a `decide=` value."""
    if source.startswith("model:"):
        return source
    if source in ("cache", "fallback"):
        return source
    return "rules"  # structure, rule, guard, finish, budget, none
