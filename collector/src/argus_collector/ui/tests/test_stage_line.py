"""Jono says what the walk is doing now: `yhteystiedot-sivu 2/8 · 00:41` (TZ v4.0 4.2)."""

from __future__ import annotations

from argus_collector.scheduler.contract import QueueRow, QueueView
from argus_collector.ui import queue_lines
from argus_collector.ui import repository as ui_repo


def _row(stage: str) -> QueueRow:
    return QueueRow("job-1", "Fixture Oy", "running", stage, 3, 6, 2, 0, "", "", "")


def test_the_running_company_shows_its_page_class_number_and_clock() -> None:
    msgs = ui_repo.load_messages()
    props = queue_lines.queue_props(msgs, QueueView([_row("contact|2|8|41")], "done", "", True))
    assert props.rows[0][1] == "yhteystiedot-sivu 2/8 · 00:41"


def test_a_captcha_form_page_is_named_as_one() -> None:
    msgs = ui_repo.load_messages()
    props = queue_lines.queue_props(msgs, QueueView([_row("form|3|8|125")], "done", "", True))
    assert props.rows[0][1] == "lomake-sivu 3/8 · 02:05", "minutes and seconds, not raw seconds"


def test_a_queued_company_keeps_its_plain_stage() -> None:
    msgs = ui_repo.load_messages()
    props = queue_lines.queue_props(msgs, QueueView([_row("queued")], "done", "", True))
    assert props.rows[0][1] == msgs.t("stage.queued")
    blank = queue_lines.queue_props(msgs, QueueView([_row("")], "done", "", True))
    assert blank.rows[0][1] == "", "a delivered company has no stage"
