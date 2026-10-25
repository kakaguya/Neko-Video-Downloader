from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class FormatInfo:
    format_id: str
    ext: str
    resolution: str
    fps: str
    filesize: str
    tbr: str
    vcodec: str
    acodec: str
    protocol: str
    note: str
    has_video: bool
    has_audio: bool

    @property
    def stream_kind(self) -> str:
        if self.has_video and self.has_audio:
            return "音视频"
        if self.has_video:
            return "视频"
        if self.has_audio:
            return "音频"
        return "其他"


@dataclass(frozen=True, slots=True)
class VideoInfo:
    title: str
    uploader: str
    duration_text: str
    webpage_url: str
    formats: tuple[FormatInfo, ...]
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DownloadRequest:
    url: str
    output_dir: Path
    cookie_file: Path | None
    format_selector: str
    needs_merge: bool = False


@dataclass(frozen=True, slots=True)
class ProgressInfo:
    percent: float | None
    status_text: str
    speed: str = ""
    eta: str = ""
    filename: str = ""


@dataclass(frozen=True, slots=True)
class JavascriptRuntime:
    name: str
    path: str
    version: str
    supported: bool
    reason: str = ""

    @property
    def display_name(self) -> str:
        return self.name.capitalize() if self.name != "deno" else "Deno"


@dataclass(frozen=True, slots=True)
class SystemSnapshot:
    python_version: str
    yt_dlp_version: str
    ffmpeg_path: str | None
    ffprobe_path: str | None
    js_runtime: JavascriptRuntime | None
    ejs_version: str | None
    executable: str

    @property
    def ffmpeg_ready(self) -> bool:
        return bool(self.ffmpeg_path and self.ffprobe_path)

    @property
    def javascript_runtime(self) -> str | None:
        """Backward-compatible human readable JS runtime description."""
        if not self.js_runtime:
            return None
        version = f" {self.js_runtime.version}" if self.js_runtime.version else ""
        return f"{self.js_runtime.name}{version}: {self.js_runtime.path}"

    @property
    def youtube_js_ready(self) -> bool:
        return bool(self.js_runtime and self.js_runtime.supported and self.ejs_version)


def format_bytes(value: int | float | None) -> str:
    if not value:
        return "未知"
    size = float(value)
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} TiB"


def format_duration(seconds: Any) -> str:
    try:
        total = max(0, int(seconds))
    except (TypeError, ValueError):
        return "未知"
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"
