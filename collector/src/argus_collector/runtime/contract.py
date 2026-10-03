"""Single entry point of the `runtime` module.

Other modules import only from here: paths of the user data directory,
the VERSION file, the build info written by install.ps1 and the kill switch.
"""

from __future__ import annotations

from pathlib import Path

from argus_collector.runtime import repository, service
from argus_collector.runtime.service import (
    BuildInfo,
    Config,
    VersionStatus,
    finnish_stamp,
    version_line,
)

__all__ = [
    "BuildInfo",
    "Config",
    "VersionStatus",
    "browser_profile_dir",
    "current_version_status",
    "load_config",
    "finnish_stamp",
    "repo_root",
    "stop_files",
    "stop_reason",
    "user_data_dir",
    "version_line",
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
