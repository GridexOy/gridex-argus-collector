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


# A bot check (TZ_SELAIN 8.5): one word or a short page is not enough, at
# least two independent signals of title, body text and challenge elements.
CHALLENGE_TITLES = (
    "just a moment", "checking your browser", "attention required", "please wait",
    "verifying", "one moment", "security check", "ddos", "bot protection", "are you a robot",
)
CHALLENGE_TEXTS = (
    "checking your browser", "verify you are human", "verifying you are human",
    "enable javascript and cookies", "this process is automatic", "ddos protection",
    "are you a robot", "not a robot", "security check", "complete the security",
    "browser verification", "request is being verified", "human verification",
)
CHALLENGE_MAX_TEXT = 2500


def is_challenge(signals: object) -> bool:
    """True for an interstitial bot check page (the CHALLENGE_JS result)."""
    if not isinstance(signals, dict):
        return False
    title = str(signals.get("title", "")).lower()
    text = str(signals.get("text", "")).lower()
    length = int(signals.get("length", 0) or 0)
    markers = signals.get("markers") or []
    hits = (
        any(p in title for p in CHALLENGE_TITLES)
        + any(p in text for p in CHALLENGE_TEXTS)
        + bool(markers)
    )
    return hits >= 2 and length < CHALLENGE_MAX_TEXT
