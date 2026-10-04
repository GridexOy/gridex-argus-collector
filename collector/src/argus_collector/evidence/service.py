"""Pure evidence logic: canonical text, hashes, spans, snapshot description."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

INLINE_WS = re.compile(r"[ \t\f\v ]+")
NON_WS_RUN = re.compile(r"\S+")


@dataclass(frozen=True)
class TextSpan:
    """Locator `text_span` (TZ section 8.12): code points `[start, end)` in the
    canonical text whose sha256 is `text_sha256`; `quote` is the exact text there."""

    start: int
    end: int
    quote: str
    text_sha256: str


@dataclass(frozen=True)
class Snapshot:
    evidence_id: str  # sha256 of the html bytes (utf-8)
    url: str
    final_url: str
    fetched_at: str  # ISO 8601 UTC
    html_sha256: str
    text_sha256: str
    html_path: Path
    text_path: Path
    html_bytes: int = 0  # length of the utf-8 html, the exact bytes uploaded to ARGUS


@dataclass(frozen=True)
class StoredSnapshot:
    """A snapshot read back from disk: the exact bytes that were hashed."""

    evidence_id: str
    url: str
    final_url: str
    fetched_at: str
    html: bytes
    html_sha256: str
    text: str
    text_sha256: str


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stored_snapshot(row: dict[str, str], html: bytes, text: str) -> StoredSnapshot:
    return StoredSnapshot(
        evidence_id=row["evidence_id"],
        url=row["url"],
        final_url=row["final_url"],
        fetched_at=row["fetched_at"],
        html=html,
        html_sha256=sha256_bytes(html),
        text=text,
        text_sha256=sha256_text(text),
    )


def canonical_text(text: str) -> str:
    normalized = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    lines = [INLINE_WS.sub(" ", line).strip() for line in normalized.split("\n")]
    return "\n".join(line for line in lines if line)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _loose_pattern(quote: str) -> re.Pattern[str] | None:
    words = NON_WS_RUN.findall(quote)
    if not words:
        return None
    return re.compile(r"\s+".join(re.escape(w) for w in words))


def find_span(text: str, quote: str) -> TextSpan | None:
    digest = sha256_text(text)
    needle = quote.strip()
    if not needle:
        return None
    start = text.find(needle)
    if start >= 0:
        return TextSpan(start, start + len(needle), needle, digest)
    pattern = _loose_pattern(needle)
    if pattern is None:
        return None
    match = pattern.search(text)
    if match is None:
        return None
    return TextSpan(match.start(), match.end(), match.group(0), digest)


def snapshot_paths(base_dir: Path, html_sha256: str) -> tuple[Path, Path]:
    folder = base_dir / html_sha256[:2]
    return folder / f"{html_sha256}.html", folder / f"{html_sha256}.txt"


def describe_snapshot(url: str, final_url: str, html: str, text: str, base_dir: Path) -> Snapshot:
    html_sha = sha256_text(html)
    html_path, text_path = snapshot_paths(base_dir, html_sha)
    return Snapshot(
        evidence_id=html_sha,
        url=url,
        final_url=final_url,
        fetched_at=datetime.now(UTC).isoformat(timespec="seconds"),
        html_sha256=html_sha,
        text_sha256=sha256_text(text),
        html_path=html_path,
        text_path=text_path,
        html_bytes=len(html.encode("utf-8")),
    )
