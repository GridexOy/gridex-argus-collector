"""Pure decisions of the browser module: how the work browser is launched."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

CHROME_CHANNEL = "chrome"
WINDOW_SIZE = "1280,900"
# K10 step 1 (owner 06.10.2026): the exhibition's market, whatever the language of Windows
# (Wera and OMICRON answered Accept-Language ru with /ru/).
# Playwright's `locale` would send a bare `fi-FI` with every navigation, so the language
# is Chrome's (`--lang`, `--accept-lang`: navigator.language fi-FI) and the header explicit.
LOCALE = "fi-FI"
ACCEPT_LANGUAGE = "fi,sv;q=0.8,en;q=0.6"
LANGUAGES = "fi-FI,fi,sv,en"
TIMEZONE = "Europe/Helsinki"
CONTEXT_ONLY = ("timezone_id", "extra_http_headers")  # not `browser.launch` options


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
    args = [f"--window-size={WINDOW_SIZE}", f"--lang={LOCALE}", f"--accept-lang={LANGUAGES}"]
    channel = CHROME_CHANNEL if windows else None
    return LaunchPlan(user_data_dir=profile_dir, headless=headless, channel=channel, args=args)


def launch_kwargs(plan: LaunchPlan) -> dict[str, object]:
    kwargs: dict[str, object] = {
        "user_data_dir": str(plan.user_data_dir),
        "headless": plan.headless,
        "args": list(plan.args),
        "no_viewport": True,
        **context_kwargs(),
    }
    if plan.channel:
        kwargs["channel"] = plan.channel
    return kwargs


def context_kwargs() -> dict[str, object]:
    """Accept-Language and time zone of every context of the collection."""
    return {"timezone_id": TIMEZONE, "extra_http_headers": {"Accept-Language": ACCEPT_LANGUAGE}}


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


def challenge_hits(signals: object) -> int:
    """Bot-check signs of a short page (title, text, markers), 0 for a long page."""
    if not isinstance(signals, dict):
        return 0
    title = str(signals.get("title", "")).lower()
    text = str(signals.get("text", "")).lower()
    length = int(signals.get("length", 0) or 0)
    markers = signals.get("markers") or []
    hits = (
        any(p in title for p in CHALLENGE_TITLES)
        + any(p in text for p in CHALLENGE_TEXTS)
        + bool(markers)
    )
    return int(hits) if length < CHALLENGE_MAX_TEXT else 0


def is_challenge(signals: object) -> bool:
    """True for an interstitial bot check page (the CHALLENGE_JS result)."""
    return challenge_hits(signals) >= 2


# Cookie banners (TZ_SELAIN 8.5): automatic, the necessary cookies preferred.
CONSENT_NECESSARY = (
    "vain välttämättömät", "välttämättömät", "only necessary", "necessary only",
    "necessary cookies only", "accept necessary", "use necessary", "essential only",
    "only essential", "nur notwendige", "nur erforderliche", "endast nödvändiga", "nödvändiga",
    "kun nødvendige", "bare nødvendige",
)
CONSENT_REJECT = (
    "hylkää", "kieltäydy", "reject", "decline", "deny", "refuse", "ablehnen", "avvisa", "neka",
    "afvis", "avslå",
)
CONSENT_ACCEPT = (
    "hyväksy kaikki", "hyväksy", "accept all", "allow all", "accept", "agree", "alle akzeptieren",
    "akzeptieren", "godkänn alla", "acceptera", "godta", "ok",
)
CONSENT_ORDER = (("necessary", CONSENT_NECESSARY), ("reject", CONSENT_REJECT),
                 ("accept", CONSENT_ACCEPT))


def consent_choice(buttons: object) -> tuple[int, str, str] | None:
    """(button index, kind necessary | reject | accept, its text) or None (no banner)."""
    if not isinstance(buttons, list):
        return None
    labels = [(int(b.get("index", -1)), str(b.get("text", "")))
              for b in buttons if isinstance(b, dict)]
    for kind, words in CONSENT_ORDER:
        for index, text in labels:
            folded = text.casefold()
            if folded and any(re.search(rf"(?<!\w){re.escape(w)}(?!\w)", folded) for w in words):
                return index, kind, text
    return None
