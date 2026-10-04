"""Jono and Lahetys props: every state, reason and ARGUS code is shown in words."""

from __future__ import annotations

import pytest

from argus_collector.scheduler.contract import DeliveryView, QueueRow, QueueView
from argus_collector.ui import queue_lines, repository


@pytest.fixture
def msgs() -> repository.Messages:
    return repository.load_messages()


def row(**changes: object) -> QueueRow:
    base: dict[str, object] = {
        "job_id": "j1", "company": "Katsa Oy", "state": "running", "stage": "browser",
        "persons": 2, "channels": 5, "sources": 3, "rejected": 0, "reject_code": "",
        "completion_reason": "", "detail": "",
    }
    return QueueRow(**{**base, **changes})  # type: ignore[arg-type]


def test_every_key_has_a_finnish_text(msgs: repository.Messages) -> None:
    tables = (queue_lines.STAGE_KEYS, queue_lines.STATE_KEYS, queue_lines.REASON_KEYS,
              queue_lines.REJECT_KEYS, queue_lines.TRANSPORT_KEYS)
    keys = [k for table in tables for k in table.values()]
    for key in [*keys, *queue_lines.COLUMN_KEYS, "delivery.rejected.other"]:
        assert msgs.t(key, code="x", n=1) != key, key


def test_tila_shows_state_reason_and_rejection_in_words(msgs: repository.Messages) -> None:
    done = row(state="partial", stage="", completion_reason="unresolved_access",
               rejected=2, reject_code="host_not_approved")
    text = queue_lines.tila(msgs, done)
    assert text.startswith(msgs.t("job.state.partial"))
    assert msgs.t("job.reason.unresolved_access") in text
    assert msgs.t("delivery.rejected.host_not_approved") in text
    assert "host_not_approved" not in text, "a known code is shown in words only"
    assert "weird_code" in queue_lines.rejection_text(msgs, "weird_code")


def test_queue_props_states_and_row_levels(msgs: repository.Messages) -> None:
    assert queue_lines.queue_props(msgs, None).state_text == msgs.t("queue.loading")
    failed = QueueView([], "failed", "HTTP 500", collecting=True)
    assert queue_lines.queue_props(msgs, failed).state_level == queue_lines.LEVEL_ERROR
    empty = QueueView([], "done", "", collecting=True)
    assert queue_lines.queue_props(msgs, empty).state_text == msgs.t("queue.empty")
    view = QueueView([row(), row(job_id="j2", state="failed")], "done", "", collecting=True)
    props = queue_lines.queue_props(msgs, view)
    assert props.state_text == ""
    assert props.rows[0][:5] == ("Katsa Oy", msgs.t("stage.browser"), "2", "5", "3")
    assert props.row_levels == [queue_lines.LEVEL_OK, queue_lines.LEVEL_ERROR]


def test_delivery_props_counts_and_transport(msgs: repository.Messages) -> None:
    props = queue_lines.delivery_props(msgs, DeliveryView(3, 1, 2.5, "delivery_error"))
    assert props.counts_level == queue_lines.LEVEL_ERROR
    assert props.state_text == msgs.t("delivery.state.delivery_error")
    offline = queue_lines.delivery_props(msgs, None)
    assert offline.state_text == msgs.t("delivery.state.offline")
    assert offline.state_level == queue_lines.LEVEL_WARN
