"""Pure mapping of walk events to the Keruu block: Finnish lines and table rows."""

from __future__ import annotations

from dataclasses import dataclass, field

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


def _step_line(msgs: Messages, event: WalkEvent) -> tuple[str, str]:
    if event.step == "model":
        if "failed" in event.detail:
            return msgs.t("collecting.step.modelFailed", detail=event.detail), LEVEL_ERROR
        key = MODEL_DETAIL_KEYS.get(event.detail, "collecting.step.modelAction")
        return msgs.t(key), LEVEL_INFO
    key = STEP_KEYS.get(event.step, "collecting.step.extracting")
    return msgs.t(key, url=event.detail or event.url, text=event.detail), LEVEL_INFO


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
