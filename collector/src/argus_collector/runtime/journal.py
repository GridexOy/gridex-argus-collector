"""Local journal of the collector (ARGUS20_TZ_TANDEM.md A3 item 4).

One line per event, prefixed by the channel ARGUS Lokit uses: `http`,
`browser`, `extraction`, `delivery`, `model`. No contact values and no
secrets go in: callers pass ids, counts, codes and URLs without query
strings (`safe_url`). Files `<user_data_dir>/logs/collector-YYYY-MM-DD.log`,
kept 14 days (TZ_SELAIN 10.2).
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

CHANNELS = ("http", "browser", "extraction", "delivery", "model")
KEEP_DAYS = 14
LOG_DIRNAME = "logs"
_LOCK = threading.Lock()


def safe_url(url: str) -> str:
    """URL without query string, fragment or credentials."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return "?"
    host = parts.hostname or ""
    netloc = host + (f":{parts.port}" if parts.port else "")
    return urlunsplit((parts.scheme, netloc, parts.path, "", ""))


def log_path(base: Path, moment: datetime) -> Path:
    return base / LOG_DIRNAME / f"collector-{moment:%Y-%m-%d}.log"


def write(base: Path, channel: str, message: str, moment: datetime | None = None) -> None:
    if channel not in CHANNELS:
        raise ValueError(f"unknown journal channel {channel!r}")
    now = moment or datetime.now(UTC)
    line = f"{now.isoformat(timespec='seconds')} {channel}: {' '.join(message.split())}\n"
    path = log_path(base, now)
    with _LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(line)


def prune(base: Path, today: datetime | None = None) -> int:
    """Delete journal files older than KEEP_DAYS; returns how many were removed."""
    limit = (today or datetime.now(UTC)) - timedelta(days=KEEP_DAYS)
    removed = 0
    for path in sorted((base / LOG_DIRNAME).glob("collector-*.log")):
        stamp = path.stem.removeprefix("collector-")
        try:
            day = datetime.strptime(stamp, "%Y-%m-%d").replace(tzinfo=UTC)
        except ValueError:
            continue
        if day < limit.replace(hour=0, minute=0, second=0, microsecond=0):
            path.unlink(missing_ok=True)
            removed += 1
    return removed
