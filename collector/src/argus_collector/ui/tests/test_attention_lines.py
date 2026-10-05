"""Huomio props: hidden without a job in needs_attention, owner actions otherwise."""

from __future__ import annotations

from argus_collector.scheduler.contract import AttentionItem
from argus_collector.ui import attention_lines, repository


def test_hidden_without_items_and_lines_per_item() -> None:
    msgs = repository.load_messages()
    assert attention_lines.attention_props(msgs, [], False, False) is None
    item = AttentionItem("j1", "LEDVANCE Oy", "http://ledvance.localhost/fi-fi/", "captcha")
    props = attention_lines.attention_props(msgs, [item], walking=False, browser_open=False)
    assert props is not None and props.title == "Huomio"
    assert "LEDVANCE Oy" in props.lines[0].text and "/fi-fi/" in props.lines[0].text
    assert "selaintarkistus" in props.lines[0].text
    assert props.open_label == "Avaa työselain"
    assert props.resume_label == "Jatka käsin tehdyn toimen jälkeen"
    assert props.open_enabled and props.hint is None
    busy = attention_lines.attention_props(msgs, [item], walking=True, browser_open=False)
    assert busy is not None and not busy.open_enabled and busy.hint is not None
