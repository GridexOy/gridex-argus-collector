"""What ARGUS rejected (0.4.8.1): one table row per rejected event or snapshot.

The company, the id ARGUS knows the item by (`event_id` / `evidence_id`, to
find the request in the API journal), seq, the code and its words, the
latest first. Read from the local outbox; nothing is sent.
"""

from __future__ import annotations

from argus_collector.delivery import contract as delivery

HEADER = ("| Time (UTC) | Company | Job | Kind | event_id / evidence_id | seq | Code | Reason |\n"
          "|---|---|---|---|---|---|---|---|")


def markdown(rows: list[delivery.Rejection], names: dict[str, str]) -> str:
    if not rows:
        return "No rejected events or snapshots.\n"
    lines = [f"# Rejected by ARGUS: {len(rows)}", "", HEADER]
    for r in rows:
        seq = "" if r.seq is None else str(r.seq)
        lines.append(f"| {r.at[:19]} | {names.get(r.job_id, '?')} | {r.job_id} | {r.kind}"
                     f" | {r.item_id} | {seq} | {r.code} | {delivery.reason(r.code)} |")
    return "\n".join(lines) + "\n"
