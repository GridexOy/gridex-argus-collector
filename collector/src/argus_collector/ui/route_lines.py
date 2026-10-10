"""Pure line of the Resurssit block: who decides and who reads.

S6 step 6.1 (TZ_SELAIN v4.0 4.1, owner 10.10.2026): the rules choose every step of
the walk, and one model - the card model - reads what they could not. The line says
exactly that: `Reititys: säännöt → qwen2.5:14b`, yellow when the model is not pulled
on the local endpoint. The navigation (7b) and vision (VL) models are gone.
"""

from __future__ import annotations

from dataclasses import dataclass

from argus_collector.ui.repository import Messages
from argus_collector.ui.walk_lines import LEVEL_OK, LEVEL_WARN


@dataclass(frozen=True)
class RouteHealth:
    name: str  # the card model
    listed: bool


def route_line(msgs: Messages, routes: tuple[RouteHealth, ...]) -> tuple[str, str] | None:
    """(text, level) of `Reititys: säännöt → qwen2.5:14b`; None before diagnostics."""
    if not routes:
        return None
    reader = routes[0]
    key = "resources.routes" if reader.listed else "resources.routesMissing"
    level = LEVEL_OK if reader.listed else LEVEL_WARN
    return msgs.t(key, name=reader.name), level
