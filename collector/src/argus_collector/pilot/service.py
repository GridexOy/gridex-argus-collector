"""Pure parts of the pilot report (ARGUS20_TZ_TANDEM.md pair 5, §9).

Per company: result, time, pages, actions, model calls, people and
channels, the share of `published_direct` among the collector's contact
events with a channel; the package threshold (>= 50 % of companies with a
person whose channel is neither inferred nor stale); a random sample of
phones checked against their snapshot (host in approved_hosts, the quote at
its locator). ARGUS-side metrics (Gold P / R, Nimetty henkilö, Soitettavia)
come from the Soittolista screen, not from here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

THRESHOLD = 0.5
DIRECT = "published_direct"
WEAK = ("inferred", "stale")


@dataclass(frozen=True)
class CompanyRow:
    company: str
    state: str
    reason: str
    active_seconds: float
    wall_seconds: float
    pages: int
    actions: int
    model_calls: int
    model_tokens: int
    model_ms: int
    persons: int
    channels: int
    direct: int  # person contact events ARGUS rated published_direct
    rated: int  # contact events with any channel status
    strong_person: bool  # a person with a channel that is not inferred / stale


@dataclass(frozen=True)
class PhoneCheck:
    company: str
    value: str
    url: str
    host_ok: bool
    quote_ok: bool


@dataclass(frozen=True)
class PilotReport:
    batch_id: str
    rows: list[CompanyRow] = field(default_factory=list)
    phones: list[PhoneCheck] = field(default_factory=list)

    @property
    def strong_share(self) -> float:
        return sum(r.strong_person for r in self.rows) / len(self.rows) if self.rows else 0.0

    @property
    def direct_share(self) -> float:
        rated = sum(r.rated for r in self.rows)
        return sum(r.direct for r in self.rows) / rated if rated else 0.0

    @property
    def threshold_met(self) -> bool:
        return bool(self.rows) and self.strong_share >= THRESHOLD


def finished_numbers(payload: dict[str, Any]) -> tuple[float, float, int, int]:
    """(active seconds, wall seconds, pages, browser actions) of a job.finished payload."""
    counts = payload.get("counts") if isinstance(payload.get("counts"), dict) else {}
    assert isinstance(counts, dict)
    return (float(payload.get("active_seconds", 0.0)), float(payload.get("wall_seconds", 0.0)),
            int(counts.get("pages_processed", 0)), int(counts.get("browser_actions", 0)))


def model_numbers(payloads: list[dict[str, Any]]) -> tuple[int, int, int]:
    """(calls, input + output tokens, milliseconds) of model.called payloads."""
    tokens = ms = 0
    for payload in payloads:
        usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
        assert isinstance(usage, dict)
        tokens += int(usage.get("input_tokens", 0)) + int(usage.get("output_tokens", 0))
        ms += int(usage.get("duration_ms", 0))
    return len(payloads), tokens, ms


def quote_at(text: str, html: str, quote: str, locator: dict[str, Any]) -> bool:
    """The quote is where its locator says (text_span), or in the snapshot text / html."""
    if locator.get("kind") == "text_span":
        start, end = int(locator.get("start", -1)), int(locator.get("end", -1))
        return 0 <= start <= end <= len(text) and text[start:end] == quote
    return bool(quote) and (quote in text or quote in html)
