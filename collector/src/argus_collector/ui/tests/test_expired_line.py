"""Lähetys says how many events expired with an earlier version (owner 10.10.2026)."""

from __future__ import annotations

from argus_collector.scheduler.contract import DeliveryView
from argus_collector.ui import queue_lines
from argus_collector.ui import repository as ui_repo


def test_the_panel_says_how_many_expired() -> None:
    msgs = ui_repo.load_messages()
    props = queue_lines.delivery_props(
        msgs, DeliveryView(pending=0, errors=0, p95_s=None, state="synced", expired=751))
    assert "Vanhentunut: 751" in props.counts_text
    assert "Odottaa lähetystä: 0" in props.counts_text
    assert "Lähetysvirhe: 0" in props.counts_text
    assert props.counts_level == "ok", "an expired queue is not an error"
    quiet = queue_lines.delivery_props(msgs, DeliveryView(0, 0, None, "synced"))
    assert "Vanhentunut" not in quiet.counts_text, "no line when nothing expired"
