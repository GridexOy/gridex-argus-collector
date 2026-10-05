"""Pure line of the Resurssit block: the routed models and whether they are pulled.

Owner 05.10.2026: rules first, the navigation model (7b) for next steps, the
card model (14b) for people, the vision model (VL) for screenshots. A missing
navigation model means the card model chooses the steps; a missing vision
model means no screenshot is ever looked at.
"""

from __future__ import annotations

from dataclasses import dataclass

from argus_collector.ui.repository import Messages
from argus_collector.ui.walk_lines import LEVEL_OK, LEVEL_WARN

ROLE_KEYS = {"navigation": "resources.route.navigation", "vision": "resources.route.vision"}


@dataclass(frozen=True)
class RouteHealth:
    role: str  # navigation | vision
    name: str
    listed: bool


def route_line(msgs: Messages, routes: tuple[RouteHealth, ...]) -> tuple[str, str] | None:
    """(text, level) of `Reititys: navigointi qwen2.5:7b · kuva ... puuttuu`, None without."""
    if not routes:
        return None
    items = [
        msgs.t("resources.route.ok" if r.listed else "resources.route.missing",
               role=msgs.t(ROLE_KEYS.get(r.role, "resources.route.navigation")), name=r.name)
        for r in routes
    ]
    level = LEVEL_OK if all(r.listed for r in routes) else LEVEL_WARN
    return msgs.t("resources.routes", items=" · ".join(items)), level
