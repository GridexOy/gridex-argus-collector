"""Pure props builder of the panel: facts in, Finnish strings and flags out.

The view renders props only (TZ_SELAIN section 11); every string here comes
from `collector/messages/fi.json` through `Messages.t`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from argus_collector.diagnostics.contract import (
    ChromeState,
    DiskState,
    GpuState,
    ModelState,
    Report,
)
from argus_collector.runtime.contract import VersionStatus, finnish_stamp, version_line
from argus_collector.ui.repository import Messages

LEVEL_OK = "ok"
LEVEL_WARN = "warn"
LEVEL_ERROR = "error"
LEVEL_INFO = "info"

CHROME_KEYS = {
    ChromeState.AVAILABLE: "resources.chrome.ok",
    ChromeState.MISSING: "resources.chrome.missing",
}
MODEL_KEYS = {
    ModelState.GPU: "resources.model.gpu",
    ModelState.CPU: "resources.model.cpu",
    ModelState.NONE: "resources.model.none",
}


@dataclass(frozen=True)
class Line:
    text: str
    level: str = LEVEL_OK


@dataclass(frozen=True)
class PanelProps:
    title: str
    version: Line
    connection_title: str
    connection_state: Line
    collecting_title: str
    start_label: str
    pause_label: str
    stop_label: str
    autostart_label: str
    auto_collect_label: str
    collecting_enabled: bool
    resources_title: str
    resources: list[Line] = field(default_factory=list)
    open_browser_label: str = ""
    open_browser_enabled: bool = True
    stop_banner: Line | None = None


def version_props(msgs: Messages, status: VersionStatus) -> Line:
    build = status.build
    if build is not None and build.built_at is not None:
        inner = msgs.t("version.builtAt", date=finnish_stamp(build.built_at))
    else:
        inner = msgs.t("version.notInstalled")
    text = version_line(status, inner)
    if status.error:
        return Line(f"{text} - {msgs.t('version.error', error=status.error)}", LEVEL_ERROR)
    return Line(text, LEVEL_OK)


def gpu_lines(msgs: Messages, report: Report) -> list[Line]:
    f, s = report.facts, report.states
    if s.gpu is GpuState.MISSING:
        return [Line(msgs.t("resources.gpu.missing"), LEVEL_WARN)]
    key = "resources.gpu.nvidia" if s.gpu is GpuState.NVIDIA else "resources.gpu.other"
    level = LEVEL_OK if s.gpu is GpuState.NVIDIA else LEVEL_WARN
    lines = [Line(msgs.t(key, name=f.gpu_name, driver=f.gpu_driver), level)]
    if f.gpu_memory_total_mb > 0:
        used, total = f.gpu_memory_used_mb, f.gpu_memory_total_mb
        lines.append(Line(msgs.t("resources.gpuMemory", used=used, total=total), LEVEL_OK))
    return lines


def resource_lines(msgs: Messages, report: Report) -> list[Line]:
    """Chrome, model, disk, memory, GPU lines of the Resurssit block (section 5.1)."""
    f, s = report.facts, report.states
    chrome_level = LEVEL_OK if s.chrome is ChromeState.AVAILABLE else LEVEL_ERROR
    model_level = LEVEL_OK if s.model is not ModelState.NONE else LEVEL_WARN
    disk_level = LEVEL_OK if s.disk is DiskState.OK else LEVEL_WARN
    lines = [
        Line(msgs.t("resources.os", name=f.os_name, version=f.os_version), LEVEL_INFO),
        Line(msgs.t(CHROME_KEYS[s.chrome]), chrome_level),
        Line(msgs.t(MODEL_KEYS[s.model]), model_level),
        Line(
            msgs.t("resources.disk", path=f.disk_path, free=f.disk_free_gb, pct=s.disk_used_pct),
            disk_level,
        ),
    ]
    if s.disk is DiskState.LOW:
        lines.append(Line(msgs.t("resources.diskWarning"), LEVEL_WARN))
    free_gb, total_gb = round(f.memory_free_mb / 1024, 1), round(f.memory_total_mb / 1024, 1)
    lines.append(Line(msgs.t("resources.memory", free=free_gb, total=total_gb), LEVEL_OK))
    return lines + gpu_lines(msgs, report)


def resources_props(msgs: Messages, report: Report | None, error: str | None) -> list[Line]:
    if error:
        return [Line(msgs.t("resources.error", error=error), LEVEL_ERROR)]
    if report is None:
        return [Line(msgs.t("resources.checking"), LEVEL_INFO)]
    return resource_lines(msgs, report)


def build_props(
    msgs: Messages,
    version: VersionStatus,
    report: Report | None,
    report_error: str | None,
    stop_reason: str | None,
) -> PanelProps:
    """S0 panel: no server connection exists, so collection stays disabled."""
    banner = Line(msgs.t("stop.active", files=stop_reason), LEVEL_ERROR) if stop_reason else None
    return PanelProps(
        title=msgs.t("app.name"),
        version=version_props(msgs, version),
        connection_title=msgs.t("connection.title"),
        connection_state=Line(msgs.t("connection.state.disconnected"), LEVEL_WARN),
        collecting_title=msgs.t("collecting.title"),
        start_label=msgs.t("collecting.start"),
        pause_label=msgs.t("collecting.pause"),
        stop_label=msgs.t("collecting.stop"),
        autostart_label=msgs.t("collecting.autostartWindows"),
        auto_collect_label=msgs.t("collecting.autoCollect"),
        collecting_enabled=False,
        resources_title=msgs.t("resources.title"),
        resources=resources_props(msgs, report, report_error),
        open_browser_label=msgs.t("attention.openBrowser"),
        open_browser_enabled=True,
        stop_banner=banner,
    )
