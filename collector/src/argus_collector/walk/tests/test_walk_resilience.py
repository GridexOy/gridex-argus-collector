"""A failed browser action (timeout, covered element, ...) must not erase progress."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from argus_collector.browser import contract as browser
from argus_collector.browser.contract import PageState
from argus_collector.walk import actions, contract, service
from argus_collector.walk.state import WalkState
from argus_collector.walk.tests.conftest import settings_for
from argus_collector.walk.tests.fake_policy import GoldPolicy
from collector.tests.fake_model_server import FakeModelServer


def test_a_failed_action_is_a_gap_and_the_walk_goes_on(
    site: str, tmp_path: Path, gold: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    policy = GoldPolicy(gold["persons"])
    fake = FakeModelServer(policy).start()
    real_perform = actions._perform
    calls = {"n": 0}

    def flaky_perform(
        state: WalkState, wb: browser.WalkBrowser, page: PageState, action: service.Action
    ) -> PageState:
        calls["n"] += 1
        if calls["n"] == 2:
            raise browser.ActionError("boom: locator.click timed out")
        return real_perform(state, wb, page, action)

    monkeypatch.setattr(actions, "_perform", flaky_perform)
    events: list[contract.WalkEvent] = []
    settings = settings_for(site, fake, tmp_path)
    try:
        summary = contract.run_walk(settings, events.append, lambda: False)
    finally:
        fake.stop()
    assert summary.error == "" and not summary.stopped
    assert summary.pages >= 2, "pages visited before the failed click must survive"
    assert events[-1].kind == service.EVENT_DONE
    assert not any(e.kind == service.EVENT_ERROR for e in events)
    assert [g.reason for g in summary.gaps] == ["timeout"], "the failed step is a gap"
    assert calls["n"] > 2, "the walk went on after the failure"
