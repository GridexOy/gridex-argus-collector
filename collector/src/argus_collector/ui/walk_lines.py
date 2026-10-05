"""Pure mapping of walk events to the Keruu block: Finnish lines and table rows."""

from __future__ import annotations

from dataclasses import dataclass, field

from argus_collector.diagnostics.contract import ChromeState, ModelState, Report
from argus_collector.ui.repository import Messages
from argus_collector.walk.contract import WalkEvent

LEVEL_OK = "ok"
LEVEL_WARN = "warn"
LEVEL_ERROR = "error"
LEVEL_INFO = "info"

STEP_KEYS = {
    "loading": "collecting.step.loading",
    "extracting": "collecting.step.extracting",
    "navigate": "collecting.step.navigate",
    "click": "collecting.step.click",
    "scroll": "collecting.step.scroll",
    "attention": "collecting.step.attention",
    "consent": "collecting.step.consent",
}
MODEL_DETAIL_KEYS = {
    "cards": "collecting.step.modelCards",
    "action": "collecting.step.modelAction",
}


@dataclass(frozen=True)
class CollectProps:
    site_url_label: str
    manual_note: str
    start_label: str
    pause_label: str
    stop_label: str
    autostart_label: str
    auto_collect_label: str
    start_enabled: bool
    stop_enabled: bool
    hint: str
    open_source_hint: str
    idle_status: str
    columns: list[str] = field(default_factory=list)
    local_test_label: str = ""
    local_test_enabled: bool = False


@dataclass(frozen=True)
class Activity:
    """What runs now: the panel's local test walk, ARGUS collecting, the connection."""

    walking: bool = False  # local test walk (Testaa paikallisesti)
    collecting: bool = False  # Kaynnista: ARGUS jobs are claimed and walked
    connected: bool = False  # a saved connection answered the last heartbeat


def _hint(msgs: Messages, stop_reason: str | None, ready: bool, connected: bool) -> str:
    if stop_reason:
        return msgs.t("collecting.stopFile")
    if not ready:
        return msgs.t("collecting.notReady")
    if not connected:
        return msgs.t("collecting.notConnected")
    return ""


def collect_props(
    msgs: Messages, report: Report | None, stop_reason: str | None, now: Activity
) -> CollectProps:
    """Kaynnista (ARGUS collecting) is live with a listed model, an available Chrome,
    a working connection and no STOP; the local test needs no connection. Both
    use the one work-browser profile, so only one of them runs at a time."""
    ready = (
        report is not None
        and report.states.chrome is ChromeState.AVAILABLE
        and report.states.model is not ModelState.NONE
    )
    busy = now.walking or now.collecting
    return CollectProps(
        site_url_label=msgs.t("collecting.siteUrl"),
        manual_note=msgs.t("collecting.manualNote"),
        start_label=msgs.t("collecting.start"),
        pause_label=msgs.t("collecting.pause"),
        stop_label=msgs.t("collecting.stop"),
        autostart_label=msgs.t("collecting.autostartWindows"),
        auto_collect_label=msgs.t("collecting.autoCollect"),
        start_enabled=ready and now.connected and not busy and not stop_reason,
        stop_enabled=busy,
        hint=_hint(msgs, stop_reason, ready, now.connected),
        open_source_hint=msgs.t("collecting.openSource"),
        idle_status=msgs.t("collecting.status.idle"),
        columns=[
            msgs.t("collecting.col.name"),
            msgs.t("collecting.col.title"),
            msgs.t("collecting.col.phone"),
            msgs.t("collecting.col.email"),
            msgs.t("collecting.col.source"),
        ],
        local_test_label=msgs.t("collecting.localTest"),
        local_test_enabled=ready and not busy and not stop_reason,
    )


def _step_line(msgs: Messages, event: WalkEvent) -> tuple[str, str]:
    if event.step == "model":
        if "failed" in event.detail:
            return msgs.t("collecting.step.modelFailed", detail=event.detail), LEVEL_ERROR
        key = MODEL_DETAIL_KEYS.get(event.detail, "collecting.step.modelAction")
        return msgs.t(key), LEVEL_INFO
    key = STEP_KEYS.get(event.step, "collecting.step.extracting")
    level = LEVEL_WARN if event.step == "attention" else LEVEL_INFO
    return msgs.t(key, url=event.detail or event.url, text=event.detail), level


def walk_event_line(msgs: Messages, event: WalkEvent) -> tuple[str, str] | None:
    """(text, level) for the status line, None for events without a line (contact)."""
    if event.kind == "page":
        text = msgs.t("collecting.status.page", n=event.page_no, budget=event.budget, url=event.url)
        return text, LEVEL_INFO
    if event.kind == "step":
        return _step_line(msgs, event)
    if event.kind == "stopped":
        return msgs.t("collecting.status.stopped"), LEVEL_WARN
    if event.kind == "error":
        return msgs.t("collecting.status.error", error=event.error), LEVEL_ERROR
    return None


def done_line(msgs: Messages, pages: int, contacts: int) -> tuple[str, str]:
    return msgs.t("collecting.status.done", pages=pages, contacts=contacts), LEVEL_OK


def contact_row(event: WalkEvent) -> tuple[str, str, str, str, str]:
    """Nimi, Titteli, Puhelin, Sahkoposti, Lahde for the table."""
    contact = event.contact
    if contact is None:
        return ("", "", "", "", event.url)
    return (
        contact.name.value,
        contact.title.value if contact.title else "",
        contact.phone.value if contact.phone else "",
        contact.email.value if contact.email else "",
        event.url,
    )
