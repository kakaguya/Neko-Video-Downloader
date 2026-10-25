from __future__ import annotations

import tempfile
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlparse

from .cookies import CookieSessionStore, validate_netscape_cookie_source
from .errors import ValidationError
from .models import DownloadRequest, FormatInfo, VideoInfo, format_bytes, format_duration
from .system import detect_javascript_runtime

LogCallback = Callable[[str, str], None]
ProgressHook = Callable[[dict], None]


class YtDlpLogger:
    """Keep yt-dlp output compact while still collecting format-integrity signals."""

    def __init__(self, callback: LogCallback | None = None) -> None:
        self.callback = callback
        self.diagnostics: list[str] = []

    def reset_diagnostics(self) -> None:
        self.diagnostics.clear()

    def _add_diagnostic(self, text: str) -> None:
        if text not in self.diagnostics:
            self.diagnostics.append(text)

    def _inspect(self, message: str) -> None:
        text = str(message).lower()
        if "provided youtube account cookies are no longer valid" in text or "rotated in the browser" in text:
            self._add_diagnostic(
                "YouTube 已判定当前账号 Cookie 失效/被轮换。请重新导出 cookies.txt；建议使用独立隐私窗口导出后立即关闭该会话。"
            )
        if "no supported javascript runtime" in text:
            self._add_diagnostic("未检测到 yt-dlp 可用的 JavaScript Runtime，YouTube 格式可能明显缺失。")
        if "n challenge solving failed" in text or ("challenge solving failed" in text and "formats may be missing" in text):
            self._add_diagnostic("YouTube JavaScript Challenge 解算失败，部分格式可能缺失；请检查 Deno 与 yt-dlp-ejs。")
        if "remote components challenge solver" in text and "skipped" in text:
            self._add_diagnostic("EJS challenge solver 未能使用本地组件；程序已允许 ejs:github 远程回退，请检查 GitHub 网络访问。")
        if "po token" in text and ("not provided" in text or "require" in text or "missing" in text):
            self._add_diagnostic(
                "当前缺少 PO Token。为避免解析/下载时启动外部浏览器，本应用已禁用自动 PO Token Provider 获取；Deno/EJS 仍正常工作，但部分 YouTube 格式可能被跳过。"
            )
        if "only sabr formats" in text:
            self._add_diagnostic("当前 YouTube client 仅提供 SABR 格式；在禁用 PO Token 自动获取的模式下，部分独立音视频格式可能不可用。")
        if "some formats may be missing" in text and "challenge" not in text:
            self._add_diagnostic("yt-dlp 提示部分格式可能缺失；请结合 Deno/EJS 与 PO Token 状态判断。")

    def _emit(self, level: str, message: str) -> None:
        if self.callback and message:
            self.callback(level, str(message))

    def debug(self, message: str) -> None:
        # yt-dlp routes a large amount of verbose/internal output through
        # logger.debug(). Inspect it for diagnostics, but do not flood the GUI.
        self._inspect(str(message))

    def info(self, message: str) -> None:
        self._inspect(str(message))

    def warning(self, message: str) -> None:
        self._inspect(str(message))
        self._emit("warning", str(message))

    def error(self, message: str) -> None:
        self._inspect(str(message))


def validate_url(url: str) -> str:
    normalized = url.strip()
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValidationError("请输入完整的 http:// 或 https:// 视频链接。")
    return normalized


def validate_cookie_file(cookie_file: str | Path | None) -> Path | None:
    """Validate a user-selected cookie *source* without ever modifying it."""
    return validate_netscape_cookie_source(cookie_file)

def validate_output_dir(output_dir: str | Path) -> Path:
    raw = str(output_dir).strip()
    if not raw:
        raise ValidationError("请选择下载保存目录。")
    path = Path(raw).expanduser()
    if path.exists() and not path.is_dir():
        raise ValidationError(f"保存路径不是文件夹：{path}")
    path.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path, prefix=".neko-write-test-", delete=True) as probe:
        probe.write(b"ok")
        probe.flush()
    return path.resolve()


def _load_yt_dlp():
    try:
        import yt_dlp  # type: ignore
    except ImportError as exc:
        raise RuntimeError("未安装 yt-dlp，请先执行 pip install -r requirements.txt") from exc
    return yt_dlp


def _string(value, default: str = "—") -> str:
    if value is None or value == "":
        return default
    return str(value)


def _normalized_token(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    return text or None


def _stream_presence(fmt: dict) -> tuple[bool, bool]:
    """Infer whether a yt-dlp format actually carries video/audio.

    Do not rely only on ``vcodec`` / ``acodec``.  Manifest formats can report
    a codec as ``unknown`` even when yt-dlp has already determined from the
    manifest that the corresponding elementary stream is absent.  In those
    cases ``video_ext`` / ``audio_ext`` are the stronger signal (notably
    ``audio_ext='none'`` for a video-only HLS format).
    """
    vcodec = _normalized_token(fmt.get("vcodec"))
    acodec = _normalized_token(fmt.get("acodec"))
    video_ext = _normalized_token(fmt.get("video_ext"))
    audio_ext = _normalized_token(fmt.get("audio_ext"))
    resolution = _normalized_token(fmt.get("resolution"))

    explicit_no_video = vcodec == "none" or video_ext == "none" or resolution == "audio only"
    explicit_no_audio = acodec == "none" or audio_ext == "none"

    if explicit_no_video:
        has_video = False
    else:
        has_video = bool(
            (vcodec not in (None, "none", "unknown"))
            or (video_ext not in (None, "none", "unknown"))
            or fmt.get("width")
            or fmt.get("height")
            or fmt.get("vbr")
        )

    if explicit_no_audio:
        has_audio = False
    else:
        has_audio = bool(
            (acodec not in (None, "none", "unknown"))
            or (audio_ext not in (None, "none", "unknown"))
            or resolution == "audio only"
            or fmt.get("abr")
            or fmt.get("asr")
            or fmt.get("audio_channels")
        )

    # Last-resort handling for manifests where both codec fields are unknown
    # and extension hints are missing.  A real raster resolution is strong
    # evidence of video, but it is not evidence that audio is present.
    if not has_video and not explicit_no_video and (fmt.get("width") or fmt.get("height")):
        has_video = True

    return has_video, has_audio


def _normalize_format(fmt: dict) -> FormatInfo:
    width = fmt.get("width")
    height = fmt.get("height")
    has_video, has_audio = _stream_presence(fmt)

    if width and height:
        resolution = f"{width}×{height}"
    elif _normalized_token(fmt.get("resolution")) == "audio only" or (has_audio and not has_video):
        resolution = "仅音频"
    elif fmt.get("resolution"):
        resolution = str(fmt.get("resolution"))
    else:
        resolution = "—"

    vcodec = _string(fmt.get("vcodec"), "none")
    acodec = _string(fmt.get("acodec"), "none")
    filesize = fmt.get("filesize") or fmt.get("filesize_approx")
    tbr = fmt.get("tbr")
    tbr_text = f"{float(tbr):.0f}k" if isinstance(tbr, (int, float)) else _string(tbr)
    note = fmt.get("format_note") or fmt.get("format") or ""

    return FormatInfo(
        format_id=_string(fmt.get("format_id"), "unknown"),
        ext=_string(fmt.get("ext")),
        resolution=resolution,
        fps=_string(fmt.get("fps")),
        filesize=format_bytes(filesize),
        tbr=tbr_text,
        vcodec=vcodec,
        acodec=acodec,
        protocol=_string(fmt.get("protocol")),
        note=str(note),
        has_video=has_video,
        has_audio=has_audio,
    )


def select_manual_format(formats: list[FormatInfo]) -> tuple[str, bool]:
    if not formats:
        raise ValidationError("请先在格式表中选择至少一个格式。")
    if len(formats) == 1:
        return formats[0].format_id, False
    if len(formats) > 2:
        raise ValidationError("手动模式最多选择 2 条轨道：1 条纯视频 + 1 条纯音频。")

    first, second = formats
    video_only = [item for item in (first, second) if item.has_video and not item.has_audio]
    audio_only = [item for item in (first, second) if item.has_audio and not item.has_video]
    if len(video_only) == 1 and len(audio_only) == 1:
        return f"{video_only[0].format_id}+{audio_only[0].format_id}", True
    raise ValidationError("选择 2 个格式时，必须是“1 条纯视频 + 1 条纯音频”；已含音频的视频请单独下载。")


def selector_for_mode(mode: str, *, ffmpeg_ready: bool) -> tuple[str, bool]:
    if mode == "best":
        if ffmpeg_ready:
            return "bv*+ba/b", True
        return "best", False
    if mode == "single":
        return "best[acodec!=none][vcodec!=none]/best", False
    if mode == "audio":
        return "ba/b", False
    raise ValidationError(f"未知下载模式：{mode}")


class YtDlpService:
    def __init__(
        self,
        log_callback: LogCallback | None = None,
        *,
        cookie_store_dir: Path | None = None,
    ) -> None:
        self.logger = YtDlpLogger(log_callback)
        self.cookie_sessions = CookieSessionStore(cookie_store_dir, log_callback)

    def _base_options(self, cookie_file: Path | None) -> dict:
        # YouTube's current extraction path needs both a JS runtime and EJS solver
        # scripts.  Deno is enabled by yt-dlp by default, but explicitly passing
        # the discovered executable path avoids Windows/Conda/IDE PATH mismatch.
        # ejs:github is the upstream-recommended remote fallback if the local
        # yt-dlp-ejs package is missing/outdated.
        options: dict = {
            "logger": self.logger,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": False,
            "verbose": False,
            "remote_components": {"ejs:github"},
            # Do not invoke installed PO Token provider plugins automatically.
            # In particular, browser-backed providers can open Chrome/Chromium.
            # yt-dlp documents fetch_pot=never as the policy that never fetches
            # a token from providers. Deno/EJS remain enabled independently.
            "extractor_args": {"youtube": {"fetch_pot": ["never"]}},
        }
        runtime = detect_javascript_runtime()
        if runtime and runtime.supported:
            options["js_runtimes"] = {runtime.name: {"path": runtime.path}}
        if cookie_file:
            options["cookiefile"] = str(cookie_file)
        return options

    def extract(self, url: str, cookie_file: str | Path | None = None) -> VideoInfo:
        self.logger.reset_diagnostics()
        yt_dlp = _load_yt_dlp()
        safe_url = validate_url(url)
        cookie_path = validate_cookie_file(cookie_file)
        with self.cookie_sessions.runtime_cookie(cookie_path) as runtime_cookie:
            options = self._base_options(runtime_cookie)
            options.update({"skip_download": True})
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(safe_url, download=False)
        if not info:
            raise RuntimeError("yt-dlp 没有返回视频信息。")
        if info.get("entries"):
            entries = [entry for entry in info.get("entries") or [] if entry]
            if entries:
                info = entries[0]
        formats = tuple(_normalize_format(fmt) for fmt in (info.get("formats") or []) if fmt.get("format_id"))
        if not formats:
            raise RuntimeError("解析成功，但没有获得任何可下载格式。")

        video_only = sum(item.has_video and not item.has_audio for item in formats)
        audio_only = sum(item.has_audio and not item.has_video for item in formats)
        muxed = sum(item.has_video and item.has_audio for item in formats)
        if muxed and not video_only and not audio_only:
            self.logger._add_diagnostic(
                "本次 yt-dlp 返回的可识别媒体流全部为音视频混流；这可能是当前 YouTube client/PO Token/SABR "
                "响应所致，而不是 GUI 主动过滤了纯音频或纯视频。可用同一 Cookie 执行 yt-dlp -v -F 对比。"
            )

        return VideoInfo(
            title=str(info.get("title") or "未命名视频"),
            uploader=str(info.get("uploader") or info.get("channel") or "未知作者"),
            duration_text=format_duration(info.get("duration")),
            webpage_url=str(info.get("webpage_url") or safe_url),
            formats=formats,
            diagnostics=tuple(self.logger.diagnostics),
        )

    def download(self, request: DownloadRequest, progress_hook: ProgressHook | None = None) -> None:
        self.logger.reset_diagnostics()
        yt_dlp = _load_yt_dlp()
        safe_url = validate_url(request.url)
        output_dir = validate_output_dir(request.output_dir)
        cookie_path = validate_cookie_file(request.cookie_file)
        with self.cookie_sessions.runtime_cookie(cookie_path) as runtime_cookie:
            options = self._base_options(runtime_cookie)
            options.update(
                {
                    "format": request.format_selector,
                    "outtmpl": str(output_dir / "%(title).180B [%(id)s].%(ext)s"),
                    "continuedl": True,
                    "overwrites": False,
                    "restrictfilenames": False,
                }
            )
            if progress_hook:
                options["progress_hooks"] = [progress_hook]
            with yt_dlp.YoutubeDL(options) as ydl:
                result = ydl.download([safe_url])
        if result not in (0, None):
            raise RuntimeError(f"yt-dlp 返回非零状态码：{result}")
