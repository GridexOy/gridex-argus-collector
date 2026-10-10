"""Pure props of the Jono and Lahetys blocks (TZ_SELAIN 5.1, TZ_TANDEM A2.4, A2.7).

Everything shown comes from the scheduler's local SQLite views; a code from
ARGUS (`rejected` + code) is shown in words in the company's row.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from argus_collector.scheduler.contract import DeliveryView, QueueRow, QueueView
from argus_collector.ui.repository import Messages

LEVEL_OK, LEVEL_WARN, LEVEL_ERROR, LEVEL_INFO = "ok", "warn", "error", "info"

STAGE_KEYS = {
    "queued": "stage.queued",
    "http": "stage.http",
    "browser": "stage.browser",
    "documents": "stage.documents",
    "finalizing": "stage.finalizing",
}
STATE_KEYS = {
    "completed": "job.state.completed",
    "partial": "job.state.partial",
    "failed": "job.state.failed",
    "cancelled": "job.state.cancelled",
    "paused": "job.state.paused",
    "needs_attention": "job.state.needs_attention",
    "stopped": "job.state.stopped",
    "waiting_lease": "job.state.waitingLease",
}
REASON_KEYS = {
    "no_contacts_in_checked_scope": "job.reason.no_contacts_in_checked_scope",
    "budget_reached": "job.reason.budget_reached",
    "unresolved_access": "job.reason.unresolved_access",
    "unsupported_source": "job.reason.unsupported_source",
    "technical_failure": "job.reason.technical_failure",
}
REJECT_KEYS = {
    "host_not_approved": "delivery.rejected.host_not_approved",
    "evidence_missing": "delivery.rejected.evidence_missing",
    "evidence_hash_mismatch": "delivery.rejected.evidence_hash_mismatch",
    "field_audit_missing": "delivery.rejected.field_audit_missing",
    "invalid_input": "delivery.rejected.invalid_input",
    "schema_unsupported": "delivery.rejected.schema_unsupported",
    "payload_too_large": "delivery.rejected.payload_too_large",
    "idempotency_conflict": "delivery.rejected.idempotency_conflict",
    "lease_expired": "delivery.rejected.lease_expired",
    "lease_mismatch": "delivery.rejected.lease_mismatch",
    "job_cancelled": "delivery.rejected.job_cancelled",
    "budget_exceeded": "delivery.rejected.budget_exceeded",
    "participation_not_confirmed": "delivery.rejected.participation_not_confirmed",
}
RULE_KEYS = {  # RefusalDetail.rule of contract 3.1.0
    "person_without_name": "delivery.rule.person_without_name",
    "no_channel": "delivery.rule.no_channel",
    "channel_value_unreadable": "delivery.rule.channel_value_unreadable",
    "snapshot_missing": "delivery.rule.snapshot_missing",
    "quote_not_found": "delivery.rule.quote_not_found",
    "value_not_in_quote": "delivery.rule.value_not_in_quote",
    "job_mismatch": "delivery.rule.job_mismatch",
}
COLUMN_KEYS = (
    "queue.col.company",
    "queue.col.stage",
    "queue.col.persons",
    "queue.col.channels",
    "queue.col.sources",
    "queue.col.state",
)
TRANSPORT_KEYS = {
    "synced": "delivery.state.synced",
    "syncing": "delivery.state.syncing",
    "offline": "delivery.state.offline",
    "delivery_error": "delivery.state.delivery_error",
}
TRANSPORT_LEVELS = {
    "synced": LEVEL_OK,
    "syncing": LEVEL_INFO,
    "offline": LEVEL_WARN,
    "delivery_error": LEVEL_ERROR,
}


@dataclass(frozen=True)
class QueueProps:
    title: str
    columns: list[str]
    rows: list[tuple[str, str, str, str, str, str]] = field(default_factory=list)
    row_levels: list[str] = field(default_factory=list)
    state_text: str = ""  # Ladataan / lataus epaonnistui / Ei tehtavia; "" with a table
    state_level: str = LEVEL_INFO


@dataclass(frozen=True)
class DeliveryProps:
    title: str
    counts_text: str
    counts_level: str
    state_text: str
    state_level: str


def rejection_text(msgs: Messages, code: str) -> str:
    """Words of a code, or of the rule a 1.2 refusal names (`invalid_input/no_channel`)."""
    code, _, rule = code.partition("/")
    if rule in RULE_KEYS:
        return msgs.t(RULE_KEYS[rule])
    key = REJECT_KEYS.get(code)
    if key:
        return msgs.t(key)
    status = code[5:] if code.startswith("http_") else ""
    if status.isdigit():
        key = "delivery.serverError" if int(status) >= 500 else "delivery.rejected.http"
        return msgs.t(key, status=status)
    return msgs.t("delivery.rejected.other", code=code)


def tila(msgs: Messages, row: QueueRow) -> str:
    parts = []
    if row.state in STATE_KEYS:
        parts.append(msgs.t(STATE_KEYS[row.state]))
    if row.state in ("partial", "failed", "completed") and row.completion_reason in REASON_KEYS:
        parts.append(msgs.t(REASON_KEYS[row.completion_reason]))
    if row.rejected:
        reason = rejection_text(msgs, row.reject_code)
        parts.append(msgs.t("queue.rejected", n=row.rejected, reason=reason))
    return " · ".join(parts)


def _row(msgs: Messages, row: QueueRow) -> tuple[str, str, str, str, str, str]:
    stage = msgs.t(STAGE_KEYS[row.stage]) if row.stage in STAGE_KEYS else ""
    return (row.company, stage, str(row.persons), str(row.channels), str(row.sources),
            tila(msgs, row))


def queue_props(msgs: Messages, view: QueueView | None) -> QueueProps:
    columns = [msgs.t(key) for key in COLUMN_KEYS]
    title = msgs.t("queue.title")
    if view is None or (not view.rows and view.claim_state == "loading"):
        return QueueProps(title, columns, state_text=msgs.t("queue.loading"))
    if not view.rows:
        if view.claim_state == "failed":
            return QueueProps(title, columns, state_text=msgs.t("queue.loadError"),
                              state_level=LEVEL_ERROR)
        return QueueProps(title, columns, state_text=msgs.t("queue.empty"))
    levels = [
        LEVEL_ERROR if r.rejected or r.state == "failed" else LEVEL_OK for r in view.rows
    ]
    failed = view.claim_state == "failed"  # WINLOG 06.10: also above a table already shown
    return QueueProps(title, columns, [_row(msgs, r) for r in view.rows], levels,
                      msgs.t("queue.claimFailed") if failed else "", LEVEL_ERROR)


def delivery_props(msgs: Messages, view: DeliveryView | None) -> DeliveryProps:
    title = msgs.t("delivery.title")
    view = view or DeliveryView(0, 0, None, "offline")
    p95 = view.p95_s
    p95_text = msgs.t("delivery.p95", s=p95) if p95 is not None else msgs.t("delivery.p95none")
    errors = msgs.t("delivery.error", n=view.errors)
    if view.errors and view.last_code:
        errors = msgs.t("delivery.errorReason", n=view.errors,
                        reason=rejection_text(msgs, view.last_code))
    parts = [msgs.t("delivery.pending", n=view.pending), errors, p95_text]
    if view.expired:
        parts.append(msgs.t("delivery.expired", n=view.expired))
    if view.server_error:
        parts.append(msgs.t("delivery.serverError", status=view.server_error))
    state_key = TRANSPORT_KEYS.get(view.state, TRANSPORT_KEYS["syncing"])
    level = LEVEL_ERROR if view.errors or view.server_error else LEVEL_OK
    return DeliveryProps(
        title, " · ".join(parts), level, msgs.t(state_key),
        TRANSPORT_LEVELS.get(view.state, LEVEL_INFO),
    )
