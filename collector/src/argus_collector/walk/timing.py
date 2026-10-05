"""Where the time of a walk goes: one journal line per observed page state
(`browser: job <id>: timing <url> ...`).

Phases (milliseconds, `time.monotonic`): `load` (navigation or click until
the page is ready: the bot-check wait and the cookie banner included),
`snapshot` (canonical text, evidence file, `source.processed`), `extract`
(channels, sections, offices, findings), `cards` (the person-card model
call), `bind` (DOM binding of the people), `record` (local rows + outbox in
one transaction), `action` (choosing the next step: rules, the decision
cache or the navigation model). `decide` names who chose the step (a
structure rule, a link rule, the cache, a model by name, the fallback or
finish) and `reader` who read the person cards (a model by name, JSON-LD,
skip, cache). `python -m argus_collector.pilot timing` sums the lines.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

from argus_collector.runtime import contract as runtime

PHASES = ("load", "snapshot", "extract", "cards", "bind", "record", "action")
CHANNEL = "browser"  # the journal channels are the ones ARGUS Lokit uses


@dataclass
class PageTiming:
    ms: dict[str, int] = field(default_factory=dict)
    decide: str = ""
    cards: str = ""  # who read the person cards: model name, jsonld, skip, cache

    def add(self, phase: str, elapsed_ms: int) -> None:
        self.ms[phase] = self.ms.get(phase, 0) + max(0, elapsed_ms)

    def total(self) -> int:
        return sum(self.ms.values())


@contextmanager
def timed(timing: PageTiming, phase: str) -> Iterator[None]:
    start = time.monotonic()
    try:
        yield
    finally:
        timing.add(phase, int((time.monotonic() - start) * 1000))


def line(job_id: str, url: str, timing: PageTiming) -> str:
    """`job <id>: timing <url> load=812 snapshot=40 ... total=1903 decide=rule reader=skip`."""
    parts = [f"{phase}={timing.ms.get(phase, 0)}" for phase in PHASES]
    who = f" decide={timing.decide or 'none'} reader={timing.cards or 'none'}"
    return f"job {job_id or 'local'}: timing {runtime.safe_url(url)} {' '.join(parts)}" \
        f" total={timing.total()}{who}"


def flush(job_id: str, url: str, timing: PageTiming) -> None:
    runtime.journal(CHANNEL, line(job_id, url, timing))
