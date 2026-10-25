from __future__ import annotations

import importlib.metadata
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

from .models import JavascriptRuntime, SystemSnapshot

_DENO_MIN = (2, 3, 0)
_NODE_MIN = (22, 0, 0)
_BUN_MIN = (1, 2, 11)
_BUN_MAX = (1, 3, 14)


def _package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def current_yt_dlp_version() -> str:
    return _package_version("yt-dlp") or "未安装"


def current_ejs_version() -> str | None:
    return _package_version("yt-dlp-ejs")


def build_yt_dlp_update_command(channel: str = "stable") -> list[str]:
    """Update yt-dlp together with its default extras, including yt-dlp-ejs."""
    normalized = channel.strip().lower()
    command = [sys.executable, "-m", "pip", "install", "-U"]
    if normalized == "nightly":
        command.append("--pre")
    elif normalized != "stable":
        raise ValueError(f"不支持的更新通道：{channel}")
    command.append("yt-dlp[default]")
    return command


def _numeric_version(text: str) -> tuple[int, ...] | None:
    match = re.search(r"(?<!\d)(\d+)(?:\.(\d+))?(?:\.(\d+))?", text)
    if not match:
        return None
    return tuple(int(part or 0) for part in match.groups())


def _run_version(path: str, *args: str) -> str:
    try:
        result = subprocess.run(
            [path, *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=4,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return (result.stdout or "").strip()


def _probe_deno(path: str) -> JavascriptRuntime:
    output = _run_version(path, "--version")
    first = output.splitlines()[0] if output else ""
    parsed = _numeric_version(first)
    version = ".".join(str(x) for x in parsed) if parsed else "未知"
    supported = bool(parsed and parsed >= _DENO_MIN)
    reason = "" if supported else "yt-dlp 当前要求 Deno >= 2.3.0"
    return JavascriptRuntime("deno", path, version, supported, reason)


def _probe_node(path: str) -> JavascriptRuntime:
    output = _run_version(path, "--version")
    parsed = _numeric_version(output)
    version = ".".join(str(x) for x in parsed) if parsed else "未知"
    supported = bool(parsed and parsed >= _NODE_MIN)
    reason = "" if supported else "yt-dlp 当前要求 Node >= 22.0.0"
    return JavascriptRuntime("node", path, version, supported, reason)


def _probe_bun(path: str) -> JavascriptRuntime:
    output = _run_version(path, "--version")
    parsed = _numeric_version(output)
    version = ".".join(str(x) for x in parsed) if parsed else "未知"
    supported = bool(parsed and _BUN_MIN <= parsed <= _BUN_MAX)
    reason = "" if supported else "Bun 支持已弃用；当前支持范围为 1.2.11–1.3.14"
    return JavascriptRuntime("bun", path, version, supported, reason)


def _probe_quickjs(path: str) -> JavascriptRuntime:
    output = _run_version(path, "--version")
    # QuickJS version strings are date-like and vary by build. Let yt-dlp perform
    # the authoritative capability check; presence is still useful as a fallback.
    version = output.splitlines()[0].strip() if output else "未知"
    return JavascriptRuntime("quickjs", path, version, True)


def detect_javascript_runtime() -> JavascriptRuntime | None:
    """Return the preferred installed runtime, favoring Deno as yt-dlp recommends."""
    probes = (
        ("deno", _probe_deno),
        ("node", _probe_node),
        ("qjs", _probe_quickjs),
        ("quickjs", _probe_quickjs),
        ("bun", _probe_bun),
    )
    fallback: JavascriptRuntime | None = None
    for executable, probe in probes:
        path = shutil.which(executable)
        if not path:
            continue
        runtime = probe(path)
        if runtime.supported:
            return runtime
        if fallback is None:
            fallback = runtime
    return fallback


def system_snapshot() -> SystemSnapshot:
    return SystemSnapshot(
        python_version=platform.python_version(),
        yt_dlp_version=current_yt_dlp_version(),
        ffmpeg_path=shutil.which("ffmpeg"),
        ffprobe_path=shutil.which("ffprobe"),
        js_runtime=detect_javascript_runtime(),
        ejs_version=current_ejs_version(),
        executable=sys.executable,
    )


def reveal_in_file_manager(path: Path) -> None:
    path = path.expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    if sys.platform.startswith("win"):
        subprocess.Popen(["explorer", str(path)])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])
