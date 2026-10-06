"""What ARGUS answered to one events request, written back to the outbox.

`evidence_missing` and `sequence_gap` stay pending and `retry.py` decides what
comes next (the snapshot first, at most 3 retries, then given up); other
rejections are counted on the company's row through the hooks and are not sent
again. Contract 3.1.0 (wire 1.2): a refusal carries its rule; the stored code is then
`<code>/<rule>` (`invalid_input/person_without_name`), the rule's words go to Jono,
Lähetys and the journal with the observation and field it names.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from argus_collector.api_client import contract as api
from argus_collector.delivery import repository as repo
from argus_collector.delivery import retry
from argus_collector.delivery.hooks import DeliveryHooks
from argus_collector.runtime import contract as runtime

KEEP_PENDING = ("evidence_missing", "sequence_gap")
WAITING = "evidence_pending"  # ARGUS applies it on the snapshot's upload: verdict asked then


@dataclass
class Answer:
    """What one events answer does to the outbox (written after all results are read)."""

    updates: list[tuple[str, str, str, str | None, str | None]] = field(default_factory=list)
    gaps: list[int] = field(default_factory=list)  # sequence_gap: one journal line for all
    fills: list[tuple[sqlite3.Row, str]] = field(default_factory=list)  # seq not taken
    moved: int = 0


def apply(
    conn: sqlite3.Connection,
    hooks: DeliveryHooks,
    job_id: str,
    rows: dict[str, sqlite3.Row],
    resp: api.EventsResponse,
    elapsed_ms: int = 0,
) -> int:
    """Write the answer back; the number of events it settled or moved on (0: only
    sequence_gap or verdicts still pending - the run waits a backoff)."""
    out = Answer()
    for result in resp.results:
        _one(conn, hooks, (job_id, resp.last_contiguous_seq), rows[result.event_id], result, out)
    repo.mark_events(conn, out.updates)
    for row, shown in out.fills:  # the seq ARGUS did not take goes to a filler (Sonepar 61-101)
        why = f"{shown}, ARGUS did not take seq {row['seq']}"
        retry.give_up(conn, hooks, job_id, row, shown, resp.last_contiguous_seq, why)
    if out.gaps and not out.fills:  # refused before 0.4.8.9 and never taken: fill them now
        run_id = str(next(iter(rows.values()))["run_id"])
        out.moved += retry.reopen(conn, hooks, job_id, run_id, resp.last_contiguous_seq,
                                  min(out.gaps))
    _journal(job_id, resp, out.updates, out.gaps, elapsed_ms)
    hooks.applied(conn, job_id, resp)
    return out.moved + len(out.fills)


def _one(conn: sqlite3.Connection, hooks: DeliveryHooks, at: tuple[str, int],
         row: sqlite3.Row, result: api.EventResult, out: Answer) -> None:
    (job_id, last_seq), code, status = at, result.code or "", result.status.value
    refusal, item = result.detail, f"event {result.event_id} seq {result.seq}"
    if refusal is not None:
        item += f" [{refusal.observation_id} {refusal.field}: {refusal.message[:160]}]"
    if status == "rejected" and code == "sequence_gap":
        out.gaps.append(result.seq)
        return
    if status == "rejected" and code in KEEP_PENDING:
        retry.after_rejection(conn, hooks, job_id, row, code, last_seq)
        out.moved += 1
        return
    shown = f"{code}/{refusal.rule.value}" if refusal is not None else code
    if status == "rejected" and last_seq < result.seq:
        out.fills.append((row, shown))
        return
    if status == "rejected":
        hooks.rejected(conn, job_id, str(row["type"]), shown, item)
    waits = code == WAITING and status != "rejected"
    out.moved += 0 if waits and row["status"] == "waiting" else 1
    channel = result.channel_status.value if result.channel_status else None
    out.updates.append((result.event_id, "waiting" if waits else status, shown,
                        result.canonical_contact_id, channel))


def _journal(job_id: str, resp: api.EventsResponse,
             updates: list[tuple[str, str, str, str | None, str | None]], gaps: list[int],
             elapsed_ms: int) -> None:
    accepted = sum(1 for u in updates if u[1] != "rejected")
    runtime.journal(
        "delivery",
        f"job {job_id}: {len(resp.results)} events sent, {accepted} accepted/duplicate,"
        f" {len(updates) - accepted} rejected, last_contiguous_seq={resp.last_contiguous_seq}"
        f" in {elapsed_ms} ms",
    )
    if gaps:
        runtime.journal("delivery", f"job {job_id}: {len(gaps)} events from seq {min(gaps)}"
                        f" wait for the seq before them (sequence_gap, not counted)")
