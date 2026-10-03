"""Pure decisions of the browser module: how the work browser is launched."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

CHROME_CHANNEL = "chrome"
WINDOW_SIZE = "1280,900"


@dataclass(frozen=True)
class LaunchPlan:
    """Everything `launch_persistent_context` needs, decided without side effects."""

    user_data_dir: Path
    headless: bool
    channel: str | None
    args: list[str] = field(default_factory=list)

    @property
    def uses_installed_chrome(self) -> bool:
        return self.channel == CHROME_CHANNEL


@dataclass(frozen=True)
class LaunchResult:
    url: str
    title: str
    user_data_dir: Path
    browser_version: str


def launch_plan(profile_dir: Path, windows: bool, headless: bool = False) -> LaunchPlan:
    """Installed Chrome on Windows (TZ_SELAIN section 7), bundled Chromium elsewhere.

    Both use a persistent profile so cookies and logins survive between runs.
    """
    args = [f"--window-size={WINDOW_SIZE}"]
    channel = CHROME_CHANNEL if windows else None
    return LaunchPlan(user_data_dir=profile_dir, headless=headless, channel=channel, args=args)


def launch_kwargs(plan: LaunchPlan) -> dict[str, object]:
    kwargs: dict[str, object] = {
        "user_data_dir": str(plan.user_data_dir),
        "headless": plan.headless,
        "args": list(plan.args),
        "no_viewport": True,
    }
    if plan.channel:
        kwargs["channel"] = plan.channel
    return kwargs


def describe_failure(plan: LaunchPlan, exc: BaseException) -> str:
    """One English line the panel shows when the browser could not start."""
    where = "installed Chrome" if plan.uses_installed_chrome else "bundled Chromium"
    first = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
    return f"work browser ({where}, profile {plan.user_data_dir}) failed: {first}"
