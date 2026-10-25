from __future__ import annotations

import locale
import os
import re
import subprocess
import threading
from pathlib import Path

from PyQt5 import QtCore

from .core.errors import classify_exception
from .core.models import DownloadRequest, ProgressInfo, VideoInfo
from .core.system import build_yt_dlp_update_command, current_yt_dlp_version
from .core.yt_service import YtDlpService

_PERCENT_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)%")
_ANSI_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


class AnalyzeWorker(QtCore.QThread):
    succeeded = QtCore.pyqtSignal(object)
    failed = QtCore.pyqtSignal(object)
    log = QtCore.pyqtSignal(str, str)

    def __init__(self, url: str, cookie_file: str, cookie_store_dir: Path, parent=None) -> None:
        super().__init__(parent)
        self.url = url
        self.cookie_file = cookie_file
        self.cookie_store_dir = cookie_store_dir

    def _log(self, level: str, message: str) -> None:
        self.log.emit(level, _ANSI_RE.sub("", message))

    def run(self) -> None:
        try:
            result: VideoInfo = YtDlpService(
                self._log, cookie_store_dir=self.cookie_store_dir
            ).extract(self.url, self.cookie_file)
        except BaseException as exc:
            self.failed.emit(classify_exception(exc, context="解析视频"))
            return
        self.succeeded.emit(result)


class DownloadWorker(QtCore.QThread):
    progress = QtCore.pyqtSignal(object)
    succeeded = QtCore.pyqtSignal(str)
    cancelled = QtCore.pyqtSignal(str)
    failed = QtCore.pyqtSignal(object)
    log = QtCore.pyqtSignal(str, str)

    def __init__(self, request: DownloadRequest, cookie_store_dir: Path, parent=None) -> None:
        super().__init__(parent)
        self.request = request
        self.cookie_store_dir = cookie_store_dir
        self._cancel_event = threading.Event()

    def cancel(self) -> None:
        self._cancel_event.set()

    def _log(self, level: str, message: str) -> None:
        self.log.emit(level, _ANSI_RE.sub("", message))

    def _progress_hook(self, data: dict) -> None:
        if self._cancel_event.is_set():
            raise RuntimeError("NEKO_USER_CANCELLED")

        status = data.get("status")
        if status == "downloading":
            downloaded = data.get("downloaded_bytes") or 0
            total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
            percent: float | None = None
            if total:
                percent = max(0.0, min(100.0, float(downloaded) / float(total) * 100.0))
            else:
                match = _PERCENT_RE.search(str(data.get("_percent_str") or ""))
                if match:
                    percent = float(match.group(1))
            speed = _ANSI_RE.sub("", str(data.get("_speed_str") or "").strip())
            eta = _ANSI_RE.sub("", str(data.get("_eta_str") or "").strip())
            filename = str(data.get("filename") or "")
            self.progress.emit(ProgressInfo(percent, "正在下载", speed, eta, filename))
        elif status == "finished":
            filename = str(data.get("filename") or "")
            self.progress.emit(ProgressInfo(100.0, "下载完成，正在进行后处理…", filename=filename))

    def run(self) -> None:
        try:
            YtDlpService(
                self._log, cookie_store_dir=self.cookie_store_dir
            ).download(self.request, self._progress_hook)
        except BaseException as exc:
            if self._cancel_event.is_set() or "NEKO_USER_CANCELLED" in str(exc):
                self.cancelled.emit("下载已由用户取消。")
                return
            self.failed.emit(classify_exception(exc, context="下载视频"))
            return
        self.succeeded.emit("下载任务已完成。")


class UpdateWorker(QtCore.QThread):
    output = QtCore.pyqtSignal(str)
    succeeded = QtCore.pyqtSignal(str, str)
    failed = QtCore.pyqtSignal(object)

    def __init__(self, channel: str, parent=None) -> None:
        super().__init__(parent)
        self.channel = channel

    def run(self) -> None:
        old_version = current_yt_dlp_version()
        try:
            command = build_yt_dlp_update_command(self.channel)
            self.output.emit("执行：" + " ".join(command))
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding=locale.getpreferredencoding(False),
                errors="replace",
                bufsize=1,
                env={**os.environ, "PIP_NO_INPUT": "1", "PIP_DISABLE_PIP_VERSION_CHECK": "1"},
            )
            assert process.stdout is not None
            for line in process.stdout:
                clean = _ANSI_RE.sub("", line.rstrip())
                if clean:
                    self.output.emit(clean)
            return_code = process.wait()
            if return_code != 0:
                raise RuntimeError(f"pip 更新 yt-dlp 失败，退出码：{return_code}")
            new_version = current_yt_dlp_version()
        except BaseException as exc:
            self.failed.emit(classify_exception(exc, context="更新 yt-dlp"))
            return
        self.succeeded.emit(old_version, new_version)
