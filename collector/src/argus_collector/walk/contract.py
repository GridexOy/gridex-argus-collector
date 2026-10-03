"""Single entry point of the `walk` module: one company-site walk.

Loop (TZ_SELAIN section 8.4): load page -> snapshot -> deterministic
channels -> model parses person cards (verbatim-checked) -> model chooses
the next action from the numbered candidates (navigate link / click button /
scroll / finish) -> repeat within the page budget, same approved hosts only,
until finish, budget, STOP file or the stop callback.
"""

from __future__ import annotations

from collections.abc import Callable

from argus_collector.walk import service
from argus_collector.walk.service import WalkEvent, WalkSettings, WalkSummary

__all__ = [
    "DEFAULT_PAGE_BUDGET",
    "WalkEvent",
    "WalkSettings",
    "WalkSummary",
    "run_walk",
    "validate_start_url",
]

DEFAULT_PAGE_BUDGET = service.DEFAULT_PAGE_BUDGET


def validate_start_url(raw: str) -> str | None:
    """`https://` is added when missing; None when the text is not a site URL."""
    return service.validate_start_url(raw)


def run_walk(
    settings: WalkSettings,
    on_event: Callable[[WalkEvent], None],
    should_stop: Callable[[], bool],
) -> WalkSummary:
    """Run the walk to the end in the calling thread; never raises for walk errors.

    Every page, step, verified contact, error and the end are reported through
    `on_event`. `should_stop` is polled between steps (Pysayta, STOP file).
    """
    from argus_collector.walk import runner  # noqa: PLC0415 - Playwright loads lazily

    return runner.run(settings, on_event, should_stop)
