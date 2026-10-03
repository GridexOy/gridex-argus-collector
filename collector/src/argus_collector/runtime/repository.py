"""File-system access for runtime facts: paths, VERSION, build info, STOP.

Nothing here is cached: every call reads the disk so the panel always
shows the current state.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import yaml

VENDOR = "Gridex"
APP = "ArgusCollector"
HOME_ENV = "ARGUS_COLLECTOR_HOME"
BUILD_FILE = "build.json"
STOP_FILE = "STOP"
CONFIG_FILE = "config.yaml"
VERSION_FILE = "VERSION"


def repo_root() -> Path:
    """Root of the source tree (the directory that holds VERSION)."""
    return Path(__file__).resolve().parents[4]


def user_data_dir() -> Path:
    """Per-user data directory (TZ_SELAIN section 10.2).

    Windows: %LOCALAPPDATA%\\Gridex\\ArgusCollector. Elsewhere:
    $XDG_DATA_HOME/Gridex/ArgusCollector. ARGUS_COLLECTOR_HOME overrides both.
    """
    override = os.environ.get(HOME_ENV)
    if override:
        return Path(override)
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    else:
        base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / VENDOR / APP


def read_version_file(root: Path | None = None) -> str:
    """Raw content of VERSION, stripped. Raises FileNotFoundError when absent."""
    path = (root or repo_root()) / VERSION_FILE
    return path.read_text(encoding="utf-8").strip()


def read_build_file(data_dir: Path | None = None) -> dict[str, str] | None:
    """Parsed build.json written by install.ps1, or None when not installed."""
    path = (data_dir or user_data_dir()) / BUILD_FILE
    if not path.is_file():
        return None
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return {str(k): str(v) for k, v in raw.items()}


def config_candidates(root: Path | None = None, data_dir: Path | None = None) -> list[Path]:
    """config.yaml in the user data dir wins over the one in the source tree."""
    return [(data_dir or user_data_dir()) / CONFIG_FILE, (root or repo_root()) / CONFIG_FILE]


def read_config_file(path: Path) -> dict[str, object]:
    """Parsed YAML mapping; raises ValueError when the file is not a mapping."""
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise ValueError(f"{path}: expected a YAML mapping")
    return {str(k): v for k, v in loaded.items()}


def stop_file_candidates(root: Path | None = None, data_dir: Path | None = None) -> list[Path]:
    """Both places where the kill switch may live (CLAUDE.md rule 11)."""
    return [(root or repo_root()) / STOP_FILE, (data_dir or user_data_dir()) / STOP_FILE]


def existing_stop_files(root: Path | None = None, data_dir: Path | None = None) -> list[Path]:
    return [p for p in stop_file_candidates(root, data_dir) if p.exists()]
