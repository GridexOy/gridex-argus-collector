"""Pure logic over runtime facts: version format, build line, kill switch."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

VERSION_RE = re.compile(r"^0\.(\d+)\.(\d+)\.(\d+)$")
VERSION_PREFIX = "cv"


@dataclass(frozen=True)
class BuildInfo:
    version: str
    commit: str
    built_at: datetime | None


@dataclass(frozen=True)
class Config:
    """Settings the panel needs in S0; `config.example.yaml` documents them."""

    model_endpoint: str = "http://127.0.0.1:8080"
    test_site_port: int = 8765
    argus_base_url: str = ""
    source: str = "defaults"


@dataclass(frozen=True)
class VersionStatus:
    file_version: str
    build: BuildInfo | None
    error: str | None


def validate_version(text: str) -> str | None:
    """Return an English error for a malformed VERSION, else None."""
    if not VERSION_RE.match(text):
        return f"VERSION must look like 0.<stage>.<step>.<fix>, got {text!r}"
    return None


def parse_build(raw: dict[str, str] | None) -> BuildInfo | None:
    if raw is None:
        return None
    built_at: datetime | None = None
    stamp = raw.get("built_at", "")
    if stamp:
        built_at = datetime.fromisoformat(stamp)
    return BuildInfo(
        version=raw.get("version", ""),
        commit=raw.get("commit", "")[:7],
        built_at=built_at,
    )


def finnish_stamp(moment: datetime) -> str:
    """`3.10.2026 klo 14.32` — the format from TZ_SELAIN section 5.1."""
    return f"{moment.day}.{moment.month}.{moment.year} klo {moment.hour}.{moment.minute:02d}"


def version_status(file_version: str, raw_build: dict[str, str] | None) -> VersionStatus:
    error = validate_version(file_version)
    build = parse_build(raw_build)
    if error is None and build is not None and build.version != file_version:
        error = f"installed build is {build.version}, VERSION file says {file_version}"
    return VersionStatus(file_version=file_version, build=build, error=error)


def version_line(status: VersionStatus, inner_text: str) -> str:
    """Bottom-left text: `cv0.0.1.0 (<inner_text>) a1b2c3d`.

    `inner_text` is the Finnish stamp from `finnish_stamp` or the
    "not installed" message; the commit is appended only when known.
    """
    build = status.build
    if build is None or build.built_at is None:
        return f"{VERSION_PREFIX}{status.file_version} ({inner_text})"
    return f"{VERSION_PREFIX}{build.version} ({inner_text}) {build.commit}".rstrip()


def describe_stop(found: list[Path]) -> str | None:
    """English detail about active kill-switch files, None when none exist."""
    if not found:
        return None
    return ", ".join(str(p) for p in found)


def _section(data: dict[str, object], name: str) -> dict[str, object]:
    raw = data.get(name)
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"config section {name!r} must be a mapping")
    return {str(k): v for k, v in raw.items()}


def config_from_mapping(data: dict[str, object], source: str) -> Config:
    """Build Config from a parsed YAML mapping; unknown keys are ignored."""
    model, site, argus = (
        _section(data, "model"),
        _section(data, "test_site"),
        _section(data, "argus"),
    )
    defaults = Config()
    port = site.get("port", defaults.test_site_port)
    if not isinstance(port, int) or isinstance(port, bool) or not 0 < port < 65536:
        raise ValueError(f"test_site.port must be a port number, got {port!r}")
    return Config(
        model_endpoint=str(model.get("endpoint", defaults.model_endpoint)),
        test_site_port=port,
        argus_base_url=str(argus.get("base_url", defaults.argus_base_url) or ""),
        source=source,
    )
