"""Pure props of the Huomio block (TZ_SELAIN 5.1, 8.5; owner decision 05.10.2026).

Shown only while a job is in `needs_attention`: a bot check did not clear by
itself within 20 s. The owner opens the work browser on that page, passes
the check by hand and presses "Jatka kasin tehdyn toimen jalkeen"; the job
then walks on from where it stopped.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from argus_collector.scheduler.contract import AttentionItem
from argus_collector.ui.repository import Messages
from argus_collector.ui.service import LEVEL_INFO, LEVEL_WARN, Line

REASON_KEYS = {"captcha": "attention.reason.captcha"}


@dataclass(frozen=True)
class AttentionProps:
    title: str
    open_label: str
    resume_label: str
    lines: list[Line] = field(default_factory=list)
    open_enabled: bool = True
    hint: Line | None = None


def attention_props(
    msgs: Messages, items: list[AttentionItem], walking: bool, browser_open: bool
) -> AttentionProps | None:
    """None when no job needs the owner (the block is hidden)."""
    if not items:
        return None
    lines = [
        Line(msgs.t("attention.item", company=item.company,
                    reason=msgs.t(REASON_KEYS.get(item.reason, "attention.reason.other")),
                    url=item.url), LEVEL_WARN)
        for item in items
    ]
    hint = Line(msgs.t("attention.busy"), LEVEL_INFO) if walking else None
    return AttentionProps(
        title=msgs.t("attention.title"), open_label=msgs.t("attention.openBrowser"),
        resume_label=msgs.t("attention.resume"), lines=lines,
        open_enabled=not walking and not browser_open, hint=hint,
    )
