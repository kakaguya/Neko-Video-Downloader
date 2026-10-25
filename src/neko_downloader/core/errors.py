from __future__ import annotations

import errno
import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class UserFacingError:
    code: str
    title: str
    message: str
    details: str
    suggestions: tuple[str, ...] = ()

    def to_log_text(self) -> str:
        lines = [f"[{self.code}] {self.title}", self.message]
        if self.details:
            lines.append(f"详情：{self.details}")
        if self.suggestions:
            lines.append("建议：")
            lines.extend(f"  • {item}" for item in self.suggestions)
        return "\n".join(lines)


class ValidationError(ValueError):
    pass


def classify_exception(exc: BaseException, *, context: str = "操作") -> UserFacingError:
    raw = str(exc).strip() or exc.__class__.__name__
    text = raw.lower()

    if isinstance(exc, ValidationError):
        return UserFacingError(
            "E_INPUT",
            "输入内容不完整",
            raw,
            f"{context}尚未开始。",
            ("检查链接、保存目录和 Cookie 文件路径。",),
        )

    if "未安装 yt-dlp" in raw or "no module named 'yt_dlp'" in text:
        return UserFacingError(
            "E_YTDLP_MISSING",
            "未安装 yt-dlp",
            "当前 Python 环境中没有找到 yt-dlp。",
            raw,
            ("点击界面的“一键更新 yt-dlp”即可安装/更新。", "或在当前环境执行 python -m pip install -U \"yt-dlp[default]\"。"),
        )

    if "pip 更新 yt-dlp 失败" in raw or "no module named pip" in text:
        return UserFacingError(
            "E_UPDATE_FAILED",
            "yt-dlp 更新失败",
            "当前 Python 环境无法通过 pip 完成 yt-dlp 更新。",
            raw,
            ("确认当前环境可以联网访问 Python 包索引。", "确认当前 Python 环境包含 pip 且目录可写。", "Conda 用户请确认启动应用与安装依赖使用的是同一个环境。"),
        )

    if "yt-dlp-ejs" in text or "challenge solver script distribution" in text:
        return UserFacingError(
            "E_EJS_MISSING",
            "YouTube EJS 解算组件不可用",
            "yt-dlp 找不到可用的 JavaScript challenge solver 脚本。",
            raw,
            (
                "点击“一键更新 yt-dlp”同步安装/升级 yt-dlp[default]（包含 yt-dlp-ejs）。",
                "程序已允许 ejs:github 远程回退；若仍失败，请检查 GitHub release assets 的网络访问。",
            ),
        )

    if "javascript runtime" in text or "no supported javascript" in text:
        return UserFacingError(
            "E_JS_RUNTIME_MISSING",
            "缺少 JavaScript 运行时",
            "当前站点解析需要 JavaScript 运行时，系统未检测到可用运行时。",
            raw,
            ("优先安装 Deno >= 2.3.0，并确保应用实际能找到 deno 可执行文件。", "也可按 yt-dlp 官方说明配置 Node.js 或 QuickJS。"),
        )

    if isinstance(exc, PermissionError) or "permission denied" in text:
        return UserFacingError(
            "E_PERMISSION",
            "没有文件系统权限",
            "程序无法读写目标文件或目录。",
            raw,
            ("更换到有写入权限的下载目录。", "检查 Cookie 文件是否可读。"),
        )

    if isinstance(exc, OSError) and getattr(exc, "errno", None) == errno.ENOSPC:
        return UserFacingError(
            "E_DISK_FULL",
            "磁盘空间不足",
            "目标磁盘没有足够空间继续下载。",
            raw,
            ("释放磁盘空间后重试。", "选择容量更大的下载目录。"),
        )

    if "unsupported url" in text or "no suitable extractor" in text:
        return UserFacingError(
            "E_URL_UNSUPPORTED",
            "当前链接暂不受支持",
            "yt-dlp 没有找到适用于该链接的解析器。",
            raw,
            ("确认链接完整且可以在浏览器中打开。", "先尝试一键更新 yt-dlp，再重新解析。"),
        )

    if "provided youtube account cookies are no longer valid" in text or "rotated in the browser" in text:
        return UserFacingError(
            "E_COOKIE_ROTATED",
            "YouTube Cookie 已失效或被轮换",
            "YouTube 已不再接受当前账号 Cookie。",
            raw,
            (
                "重新导出 Netscape 格式 cookies.txt；应用会自动检测新文件并重置内部工作会话。",
                "建议使用独立隐私/无痕窗口登录，在同一标签页打开 youtube.com/robots.txt 后导出，然后立即关闭该隐私会话。",
                "不要继续用导出 Cookie 的同一浏览器会话浏览 YouTube，否则账号 Cookie 可能再次被轮换。",
            ),
        )

    auth_markers = (
        "members-only",
        "members only",
        "premium members",
        "private video",
        "age-restricted",
        "login required",
    )
    cookie_login_signal = any(token in text for token in ("sign in", "login required", "cookies", "cookie")) and any(
        token in text for token in ("required", "needed", "confirm", "authentication", "private", "member", "age")
    )
    if cookie_login_signal or any(marker in text for marker in auth_markers):
        return UserFacingError(
            "E_AUTH_REQUIRED",
            "需要登录凭据或 Cookie",
            "站点要求登录、会员权限、年龄验证或账号确认。",
            raw,
            (
                "导出当前浏览器登录会话的 Netscape 格式 cookies.txt 并在界面中选择。",
                "确认 Cookie 尚未过期，且账号本身有权观看该内容。",
            ),
        )

    if "http error 403" in text or re.search(r"\b403\b", text):
        return UserFacingError(
            "E_HTTP_403",
            "服务器拒绝访问（HTTP 403）",
            "请求被站点拒绝，通常与 Cookie、地区限制、请求特征或过旧的 yt-dlp 有关。",
            raw,
            ("先更新 yt-dlp。", "需要登录时提供有效 Cookie。", "确认浏览器中该视频在当前网络下可正常播放。"),
        )

    if "http error 429" in text or "too many requests" in text:
        return UserFacingError(
            "E_RATE_LIMIT",
            "请求过于频繁（HTTP 429）",
            "站点暂时限制了当前网络或账号的请求频率。",
            raw,
            ("稍后再试。", "避免连续反复解析同一链接。", "如站点要求登录，请使用有效 Cookie。"),
        )

    if any(token in text for token in ("geo restricted", "not available in your country", "not available in your region")):
        return UserFacingError(
            "E_GEO_BLOCK",
            "内容存在地区限制",
            "该内容在当前网络所在地区不可用。",
            raw,
            ("确认内容发行方是否允许在你所在地区访问。",),
        )

    if "requested format is not available" in text or "format is not available" in text:
        return UserFacingError(
            "E_FORMAT_UNAVAILABLE",
            "所选格式已不可用",
            "站点返回的格式列表发生变化，或当前格式需要额外条件。",
            raw,
            ("重新点击“解析格式”并重新选择。", "尝试“智能最佳”下载模式。", "更新 yt-dlp 后重试。"),
        )

    if "ffmpeg" in text and any(token in text for token in ("not found", "not installed", "required", "missing")):
        return UserFacingError(
            "E_FFMPEG_MISSING",
            "缺少 FFmpeg/ffprobe",
            "当前下载需要合并或后处理音视频，但系统没有找到 FFmpeg 工具。",
            raw,
            ("安装 FFmpeg，并确保 ffmpeg 和 ffprobe 都在 PATH 中。", "不想安装 FFmpeg 时可选择单文件/单轨格式。"),
        )

    if any(token in text for token in ("certificate verify failed", "ssl", "tls")) and "error" in text:
        return UserFacingError(
            "E_TLS",
            "HTTPS/TLS 连接失败",
            "安全连接建立失败，可能与证书、代理或系统时间有关。",
            raw,
            ("检查系统日期时间是否正确。", "检查代理/抓包软件是否替换了 HTTPS 证书。"),
        )

    if any(
        token in text
        for token in (
            "name or service not known",
            "temporary failure in name resolution",
            "network is unreachable",
            "connection refused",
            "connection reset",
            "timed out",
            "timeout",
            "unable to download webpage",
        )
    ):
        return UserFacingError(
            "E_NETWORK",
            "网络连接失败",
            "程序未能稳定连接到视频站点。",
            raw,
            ("检查网络、DNS 和代理设置。", "确认链接在浏览器中可以访问。", "稍后重试。"),
        )

    return UserFacingError(
        "E_YTDLP" if "downloaderror" in exc.__class__.__name__.lower() else "E_UNEXPECTED",
        f"{context}失败",
        "程序遇到了未能自动归类的错误。",
        raw,
        ("更新 yt-dlp 后重试。", "若问题持续，可提交错误代码、环境诊断和复现步骤。"),
    )
