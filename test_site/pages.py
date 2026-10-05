"""Page transforms of the fixture server: port placeholder, variants, bot check.

- `__PORT__` in an `.html` page becomes the port the request came in on, so
  links between two virtual hosts work on any (random) test port.
- A variant (`server.start(variant=...)`, CLI `--variant`) overlays files:
  `variants/<name>/<label>/<path>` wins over the normal file when it exists
  (`label` is the vhost label, `site` for 127.0.0.1).
- Bot check: `CHALLENGED` paths answer a JS challenge interstitial
  (`templates/challenge.html`) until the request carries the cookie
  `fixture_waf=passed`; variant `challenge-stuck` never sets it and ignores it.
"""

from __future__ import annotations

from http.cookies import CookieError, SimpleCookie
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VARIANTS_DIR = ROOT / "variants"
CHALLENGE_TEMPLATE = ROOT / "templates" / "challenge.html"
PORT_PLACEHOLDER = b"__PORT__"
SITE_LABEL = "site"
STUCK_VARIANT = "challenge-stuck"
WAF_COOKIE = "fixture_waf"
WAF_PASSED = "passed"
# vhost label -> URL path prefixes behind the JS challenge
CHALLENGED: dict[str, tuple[str, ...]] = {"ledvance": ("/fi-fi/",)}
PASS_STATEMENT = f'document.cookie = "{WAF_COOKIE}={WAF_PASSED}; path=/";'
STUCK_STATEMENT = "/* the check never completes: no cookie is set */"


def known_variants() -> list[str]:
    """Overlay folders under `variants/` plus the logic-only `challenge-stuck`."""
    folders: set[str] = set()
    if VARIANTS_DIR.is_dir():
        folders = {p.name for p in VARIANTS_DIR.iterdir() if p.is_dir()}
    return sorted(folders | {STUCK_VARIANT})


def check_variant(variant: str | None) -> str | None:
    """The variant itself, or ValueError when no such variant exists."""
    if variant is not None and variant not in known_variants():
        known = ", ".join(known_variants())
        raise ValueError(f"unknown test site variant {variant!r} (known: {known})")
    return variant


def substitute_port(body: bytes, port: str) -> bytes:
    return body.replace(PORT_PLACEHOLDER, port.encode("ascii"))


def overlay_root(variant: str | None, label: str | None) -> Path | None:
    """Overlay folder of `variant` for a host, None when it has none."""
    if variant is None:
        return None
    folder = VARIANTS_DIR / variant / (label or SITE_LABEL)
    return folder if folder.is_dir() else None


def overlay_serves(path: Path) -> bool:
    """True when the overlay has this file (or a directory index for it)."""
    return path.is_file() or (path.is_dir() and (path / "index.html").is_file())


def waf_passed(cookie_header: str) -> bool:
    cookies: SimpleCookie = SimpleCookie()
    try:
        cookies.load(cookie_header)
    except CookieError:
        return False
    morsel = cookies.get(WAF_COOKIE)
    return morsel is not None and morsel.value == WAF_PASSED


def needs_challenge(
    label: str | None, url_path: str, cookie_header: str, variant: str | None
) -> bool:
    prefixes = CHALLENGED.get(label or "", ())
    if not any(url_path.startswith(prefix) for prefix in prefixes):
        return False
    return variant == STUCK_VARIANT or not waf_passed(cookie_header)


def challenge_page(host: str, variant: str | None) -> bytes:
    """The interstitial for `host`; in `challenge-stuck` its script sets no cookie."""
    statement = STUCK_STATEMENT if variant == STUCK_VARIANT else PASS_STATEMENT
    text = CHALLENGE_TEMPLATE.read_text(encoding="utf-8")
    return text.replace("__HOST__", host).replace("__PASS__", statement).encode("utf-8")
