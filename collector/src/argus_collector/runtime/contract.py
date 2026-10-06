"""Single entry point of the `runtime` module.

Other modules import only from here: paths of the user data directory,
the VERSION file, the build info written by install.ps1 and the kill switch.
"""

from __future__ import annotations

from pathlib import Path
from typing import IO

from argus_collector.runtime import instance, repository, service
from argus_collector.runtime import journal as journal_file
from argus_collector.runtime.service import (
    BuildInfo,
    Config,
    VersionStatus,
    finnish_stamp,
    version_line,
    version_status,
)

__all__ = [
    "BuildInfo",
    "Config",
    "VersionStatus",
    "browser_profile_dir",
    "current_version_status",
    "load_config",
    "panel_lock",
    "panel_owner",
    "panel_release",
    "finnish_stamp",
    "journal",
    "prune_journal",
    "safe_url",
    "repo_root",
    "stop_files",
    "stop_reason",
    "user_data_dir",
    "version_line",
    "version_status",
]

BROWSER_PROFILE_DIRNAME = "browser-profile"


def repo_root() -> Path:
    return repository.repo_root()


def user_data_dir() -> Path:
    return repository.user_data_dir()


def browser_profile_dir() -> Path:
    """Chrome user-data-dir of the work browser (TZ_SELAIN section 7)."""
    return repository.user_data_dir() / BROWSER_PROFILE_DIRNAME


def current_version_status() -> VersionStatus:
    """VERSION file plus build.json, with a mismatch reported as `error`."""
    try:
        file_version = repository.read_version_file()
    except FileNotFoundError as exc:
        return VersionStatus(file_version="", build=None, error=f"VERSION file missing: {exc}")
    try:
        raw_build = repository.read_build_file()
    except ValueError as exc:
        return VersionStatus(file_version=file_version, build=None, error=str(exc))
    return service.version_status(file_version, raw_build)


def stop_files() -> list[Path]:
    """Existing STOP files (repo root and user data dir)."""
    return repository.existing_stop_files()


def stop_reason() -> str | None:
    return service.describe_stop(stop_files())


def load_config() -> Config:
    """First existing config.yaml (user data dir, then source tree), else defaults.

    A malformed file raises ValueError: the panel shows it, it does not guess.
    """
    for path in repository.config_candidates():
        if path.is_file():
            return service.config_from_mapping(repository.read_config_file(path), str(path))
    return Config()


JOURNAL_CHANNELS = journal_file.CHANNELS


def journal(channel: str, message: str) -> None:
    """Append one line `<UTC time> <channel>: <message>` to today's journal file.

    `channel` is one of http / browser / extraction / delivery / model (the
    prefixes of ARGUS Lokit). Never pass contact values or tokens."""
    journal_file.write(repository.user_data_dir(), channel, message)


def prune_journal() -> int:
    """Remove journal files older than 14 days."""
    return journal_file.prune(repository.user_data_dir())


def safe_url(url: str) -> str:
    """URL fit for the journal: no query string, fragment or credentials."""
    return journal_file.safe_url(url)


def panel_lock() -> IO[str] | None:
    """The one-panel lock, held open while the panel runs; None: another panel has it."""
    return instance.acquire(repository.user_data_dir())


def panel_owner() -> str:
    """Process id of the panel that holds the lock."""
    return instance.owner(repository.user_data_dir())


def panel_release(lock: IO[str]) -> None:
    """Free the one-panel lock when the panel closes."""
    instance.release(lock)
