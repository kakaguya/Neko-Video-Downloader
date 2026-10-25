from __future__ import annotations

import platform
from datetime import datetime
from pathlib import Path

from PyQt5 import QtCore, QtGui, QtWidgets

from .. import __version__
from ..core.cookies import clear_cookie_session
from ..core.errors import UserFacingError, ValidationError, classify_exception
from ..core.models import DownloadRequest, FormatInfo, ProgressInfo, VideoInfo
from ..core.system import reveal_in_file_manager, system_snapshot
from ..core.yt_service import (
    select_manual_format,
    selector_for_mode,
    validate_cookie_file,
    validate_output_dir,
    validate_url,
)
from ..workers import AnalyzeWorker, DownloadWorker, UpdateWorker


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, app_data_dir: Path, parent=None) -> None:
        super().__init__(parent)
        self.app_data_dir = Path(app_data_dir)
        self.app_data_dir.mkdir(parents=True, exist_ok=True)
        self.cookie_store_dir = self.app_data_dir / "cookie-sessions"
        self.settings = QtCore.QSettings("NekoDownloader", "NekoVideoDownloader")
        self.video_info: VideoInfo | None = None
        self.snapshot = system_snapshot()
        self.analyze_worker: AnalyzeWorker | None = None
        self.download_worker: DownloadWorker | None = None
        self.update_worker: UpdateWorker | None = None
        self._close_after_download = False

        self.setObjectName("RootWindow")
        self.setWindowTitle(f"Neko Video Downloader {__version__}")
        self.setMinimumSize(980, 680)
        screen = QtWidgets.QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            self.resize(
                max(980, min(1280, available.width() - 60)),
                max(680, min(900, available.height() - 60)),
            )
        else:
            self.resize(1240, 860)

        self._build_ui()
        self._connect_signals()
        self._restore_settings()
        self._refresh_system_badges()
        self._apply_mode_state()
        self._log("info", f"Neko Video Downloader {__version__} 已启动。")
        self._log("info", f"Python {self.snapshot.python_version} | yt-dlp {self.snapshot.yt_dlp_version}")
        if not self.snapshot.ffmpeg_ready:
            self._log("warning", "未同时检测到 ffmpeg/ffprobe；需要音视频合并的任务可能失败。")
        if not self.snapshot.js_runtime:
            self._log("warning", "未检测到 JavaScript 运行时；YouTube 格式可能明显缺失，推荐安装 Deno >= 2.3.0。")
        elif not self.snapshot.js_runtime.supported:
            self._log("warning", f"检测到 {self.snapshot.js_runtime.display_name}，但版本不受支持：{self.snapshot.js_runtime.reason}")
        if not self.snapshot.ejs_version:
            self._log("warning", "当前 Python 环境未检测到 yt-dlp-ejs；程序会允许 ejs:github 远程回退，但仍建议执行一键更新。")

    @staticmethod
    def _field_label(text: str, parent: QtWidgets.QWidget) -> QtWidgets.QLabel:
        label = QtWidgets.QLabel(text, parent)
        label.setObjectName("FieldLabel")
        return label

    @staticmethod
    def _configure_table(table: QtWidgets.QTableWidget, stretch_column: int) -> None:
        table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.setSortingEnabled(False)
        table.setShowGrid(False)
        table.setMinimumHeight(220)
        header = table.horizontalHeader()
        header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(stretch_column, QtWidgets.QHeaderView.Stretch)

    def _build_ui(self) -> None:
        root = QtWidgets.QWidget(self)
        self.setCentralWidget(root)
        root_layout = QtWidgets.QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QtWidgets.QScrollArea(root)
        scroll.setObjectName("MainScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        root_layout.addWidget(scroll)

        page = QtWidgets.QWidget(scroll)
        page.setObjectName("Root")
        scroll.setWidget(page)
        outer = QtWidgets.QVBoxLayout(page)
        outer.setContentsMargins(16, 14, 16, 12)
        outer.setSpacing(10)
        outer.setSizeConstraint(QtWidgets.QLayout.SetMinimumSize)

        # Header: deliberately keep only product identity + environment badges.
        header = QtWidgets.QFrame(page)
        header.setObjectName("HeaderCard")
        header_layout = QtWidgets.QHBoxLayout(header)
        header_layout.setContentsMargins(20, 14, 20, 14)
        header_layout.setSpacing(14)

        mascot = QtWidgets.QLabel("ฅ^•ﻌ•^ฅ", header)
        mascot_font = mascot.font()
        mascot_font.setPointSize(25)
        mascot_font.setBold(True)
        mascot.setFont(mascot_font)
        mascot.setStyleSheet("color: #f4a8d2; padding-right: 6px;")
        header_layout.addWidget(mascot)

        title = QtWidgets.QLabel("Neko Video Downloader", header)
        title.setObjectName("AppTitle")
        header_layout.addWidget(title, 1)

        self.ytdlp_badge = QtWidgets.QLabel(header)
        self.ffmpeg_badge = QtWidgets.QLabel(header)
        self.js_badge = QtWidgets.QLabel(header)
        self.python_badge = QtWidgets.QLabel(header)
        header_layout.addWidget(self.ytdlp_badge)
        header_layout.addWidget(self.ffmpeg_badge)
        header_layout.addWidget(self.js_badge)
        header_layout.addWidget(self.python_badge)
        outer.addWidget(header)

        config_card = QtWidgets.QFrame(page)
        config_card.setObjectName("Card")
        config = QtWidgets.QGridLayout(config_card)
        config.setContentsMargins(14, 11, 14, 11)
        config.setHorizontalSpacing(10)
        config.setVerticalSpacing(7)

        section = QtWidgets.QLabel("✦ 下载配置", config_card)
        section.setObjectName("SectionTitle")
        config.addWidget(section, 0, 0, 1, 4)

        config.addWidget(self._field_label("视频链接", config_card), 1, 0)
        self.url_edit = QtWidgets.QLineEdit(config_card)
        self.url_edit.setPlaceholderText("粘贴 YouTube / Bilibili / 其他 yt-dlp 支持的链接…")
        self.url_edit.setClearButtonEnabled(True)
        config.addWidget(self.url_edit, 1, 1, 1, 3)

        config.addWidget(self._field_label("Cookie（可选）", config_card), 2, 0)
        self.cookie_edit = QtWidgets.QLineEdit(config_card)
        self.cookie_edit.setPlaceholderText("仅会员、年龄验证、私人内容等需要登录时选择 cookies.txt")
        self.cookie_browse = QtWidgets.QPushButton("选择…", config_card)
        self.cookie_clear = QtWidgets.QPushButton("清空", config_card)
        self.cookie_browse.setMinimumWidth(96)
        self.cookie_clear.setMinimumWidth(88)
        config.addWidget(self.cookie_edit, 2, 1)
        config.addWidget(self.cookie_browse, 2, 2)
        config.addWidget(self.cookie_clear, 2, 3)

        config.addWidget(self._field_label("保存目录", config_card), 3, 0)
        self.output_edit = QtWidgets.QLineEdit(config_card)
        self.output_edit.setPlaceholderText("选择下载文件夹…")
        self.output_browse = QtWidgets.QPushButton("选择…", config_card)
        self.open_folder_button = QtWidgets.QPushButton("打开目录", config_card)
        self.output_browse.setMinimumWidth(96)
        self.open_folder_button.setMinimumWidth(96)
        config.addWidget(self.output_edit, 3, 1)
        config.addWidget(self.output_browse, 3, 2)
        config.addWidget(self.open_folder_button, 3, 3)

        self.analyze_button = QtWidgets.QPushButton("✦ 解析格式", config_card)
        self.analyze_button.setObjectName("PrimaryButton")
        self.update_channel = QtWidgets.QComboBox(config_card)
        self.update_channel.addItem("夜间版 nightly（官方推荐）", "nightly")
        self.update_channel.addItem("稳定版 stable", "stable")
        self.update_channel.setMinimumWidth(188)
        self.update_button = QtWidgets.QPushButton("↻ 一键更新 yt-dlp", config_card)
        self.update_button.setMinimumWidth(154)
        self.update_button.setObjectName("AccentButton")
        config.addWidget(self.analyze_button, 4, 1)
        config.addWidget(self.update_channel, 4, 2)
        config.addWidget(self.update_button, 4, 3)
        config.setColumnStretch(1, 1)
        outer.addWidget(config_card)

        # Formats: video/muxed on the left, audio-only on the right.
        format_card = QtWidgets.QFrame(page)
        format_card.setObjectName("Card")
        format_layout = QtWidgets.QVBoxLayout(format_card)
        format_layout.setContentsMargins(14, 10, 14, 11)
        format_layout.setSpacing(8)

        format_header = QtWidgets.QHBoxLayout()
        section2 = QtWidgets.QLabel("✦ 可用格式", format_card)
        section2.setObjectName("SectionTitle")
        self.video_meta_label = QtWidgets.QLabel("尚未解析视频", format_card)
        self.video_meta_label.setObjectName("Hint")
        self.format_count_label = QtWidgets.QLabel("视频 0 · 音频 0", format_card)
        self.format_count_label.setObjectName("StatusInfo")
        format_header.addWidget(section2)
        format_header.addWidget(self.video_meta_label, 1)
        format_header.addWidget(self.format_count_label)
        format_layout.addLayout(format_header)

        split = QtWidgets.QHBoxLayout()
        split.setSpacing(10)

        video_panel = QtWidgets.QFrame(format_card)
        video_panel.setObjectName("FormatPanel")
        video_layout = QtWidgets.QVBoxLayout(video_panel)
        video_layout.setContentsMargins(10, 9, 10, 10)
        video_layout.setSpacing(6)
        video_head = QtWidgets.QHBoxLayout()
        video_title = QtWidgets.QLabel("🎬 视频格式", video_panel)
        video_title.setObjectName("FormatTitle")
        self.video_count_label = QtWidgets.QLabel("0", video_panel)
        self.video_count_label.setObjectName("MiniBadge")
        video_head.addWidget(video_title)
        video_head.addStretch(1)
        video_head.addWidget(self.video_count_label)
        video_layout.addLayout(video_head)
        self.video_hint_label = QtWidgets.QLabel("左侧可选择纯视频或已含音频的单文件格式", video_panel)
        self.video_hint_label.setObjectName("PanelHint")
        video_layout.addWidget(self.video_hint_label)
        self.video_table = QtWidgets.QTableWidget(0, 7, video_panel)
        self.video_table.setObjectName("VideoFormatTable")
        self.video_table.setHorizontalHeaderLabels(["类型", "ID", "分辨率", "FPS", "封装", "大小", "视频编码"])
        self._configure_table(self.video_table, 6)
        video_layout.addWidget(self.video_table, 1)

        audio_panel = QtWidgets.QFrame(format_card)
        audio_panel.setObjectName("FormatPanel")
        audio_layout = QtWidgets.QVBoxLayout(audio_panel)
        audio_layout.setContentsMargins(10, 9, 10, 10)
        audio_layout.setSpacing(6)
        audio_head = QtWidgets.QHBoxLayout()
        audio_title = QtWidgets.QLabel("🎧 音频格式", audio_panel)
        audio_title.setObjectName("FormatTitle")
        self.audio_count_label = QtWidgets.QLabel("0", audio_panel)
        self.audio_count_label.setObjectName("MiniBadge")
        audio_head.addWidget(audio_title)
        audio_head.addStretch(1)
        audio_head.addWidget(self.audio_count_label)
        audio_layout.addLayout(audio_head)
        self.audio_hint_label = QtWidgets.QLabel("可单独下载，或与左侧纯视频自动合并", audio_panel)
        self.audio_hint_label.setObjectName("PanelHint")
        audio_layout.addWidget(self.audio_hint_label)
        self.audio_table = QtWidgets.QTableWidget(0, 5, audio_panel)
        self.audio_table.setObjectName("AudioFormatTable")
        self.audio_table.setHorizontalHeaderLabels(["ID", "封装", "码率", "大小", "音频编码"])
        self._configure_table(self.audio_table, 4)
        audio_layout.addWidget(self.audio_table, 1)

        split.addWidget(video_panel, 3)
        split.addWidget(audio_panel, 2)
        format_layout.addLayout(split, 1)

        self.selection_summary = QtWidgets.QLabel("当前选择：尚未选择格式", format_card)
        self.selection_summary.setObjectName("SelectionSummary")
        self.selection_summary.setWordWrap(True)
        format_layout.addWidget(self.selection_summary)
        outer.addWidget(format_card, 4)

        task_card = QtWidgets.QFrame(page)
        task_card.setObjectName("Card")
        task_layout = QtWidgets.QVBoxLayout(task_card)
        task_layout.setContentsMargins(14, 10, 14, 11)
        task_layout.setSpacing(7)

        task_top = QtWidgets.QHBoxLayout()
        section3 = QtWidgets.QLabel("✦ 下载任务", task_card)
        section3.setObjectName("SectionTitle")
        self.mode_combo = QtWidgets.QComboBox(task_card)
        self.mode_combo.addItem("手动组合（左右选择）", "manual")
        self.mode_combo.addItem("智能最佳（推荐）", "best")
        self.mode_combo.addItem("最佳单文件（尽量不合并）", "single")
        self.mode_combo.addItem("仅下载最佳音频", "audio")
        self.mode_combo.setMinimumWidth(190)
        self.download_button = QtWidgets.QPushButton("♡ 开始下载", task_card)
        self.download_button.setMinimumWidth(112)
        self.download_button.setObjectName("PrimaryButton")
        self.cancel_button = QtWidgets.QPushButton("取消下载", task_card)
        self.cancel_button.setMinimumWidth(92)
        self.cancel_button.setObjectName("DangerButton")
        self.cancel_button.setEnabled(False)
        task_top.addWidget(section3)
        task_top.addStretch(1)
        task_top.addWidget(self._field_label("模式", task_card))
        task_top.addWidget(self.mode_combo)
        task_top.addWidget(self.download_button)
        task_top.addWidget(self.cancel_button)
        task_layout.addLayout(task_top)

        progress_row = QtWidgets.QHBoxLayout()
        self.progress_bar = QtWidgets.QProgressBar(task_card)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("等待下载")
        self.progress_detail = QtWidgets.QLabel("速度 —  ·  ETA —", task_card)
        self.progress_detail.setObjectName("Hint")
        progress_row.addWidget(self.progress_bar, 1)
        progress_row.addWidget(self.progress_detail)
        task_layout.addLayout(progress_row)
        outer.addWidget(task_card)

        status_card = QtWidgets.QFrame(page)
        status_card.setObjectName("Card")
        status_layout = QtWidgets.QVBoxLayout(status_card)
        status_layout.setContentsMargins(14, 10, 14, 11)
        status_header = QtWidgets.QHBoxLayout()
        section4 = QtWidgets.QLabel("✦ 运行状态", status_card)
        section4.setObjectName("SectionTitle")
        self.copy_diag_button = QtWidgets.QPushButton("复制诊断信息", status_card)
        self.clear_log_button = QtWidgets.QPushButton("清空", status_card)
        self.copy_diag_button.setMinimumWidth(118)
        self.clear_log_button.setMinimumWidth(76)
        status_header.addWidget(section4)
        status_header.addStretch(1)
        status_header.addWidget(self.copy_diag_button)
        status_header.addWidget(self.clear_log_button)
        status_layout.addLayout(status_header)
        self.log_edit = QtWidgets.QPlainTextEdit(status_card)
        self.log_edit.setReadOnly(True)
        self.log_edit.setMaximumBlockCount(500)
        self.log_edit.setMinimumHeight(82)
        status_layout.addWidget(self.log_edit)
        outer.addWidget(status_card, 2)

        for widget_type in (QtWidgets.QPushButton, QtWidgets.QLineEdit, QtWidgets.QComboBox):
            for control in page.findChildren(widget_type):
                control.setMinimumHeight(34)
        for badge in (self.ytdlp_badge, self.ffmpeg_badge, self.js_badge, self.python_badge):
            badge.setMinimumHeight(34)
        header.setMinimumHeight(78)
        self.statusBar().showMessage("就绪")

    def _connect_signals(self) -> None:
        self.cookie_browse.clicked.connect(self._choose_cookie)
        self.cookie_clear.clicked.connect(self._clear_cookie)
        self.output_browse.clicked.connect(self._choose_output)
        self.open_folder_button.clicked.connect(self._open_output_folder)
        self.analyze_button.clicked.connect(self._start_analysis)
        self.update_button.clicked.connect(self._start_update)
        self.download_button.clicked.connect(self._start_download)
        self.cancel_button.clicked.connect(self._cancel_download)
        self.copy_diag_button.clicked.connect(self._copy_diagnostics)
        self.clear_log_button.clicked.connect(self.log_edit.clear)
        self.mode_combo.currentIndexChanged.connect(self._apply_mode_state)
        self.video_table.itemSelectionChanged.connect(self._on_video_selection_changed)
        self.audio_table.itemSelectionChanged.connect(self._on_audio_selection_changed)
        self.url_edit.returnPressed.connect(self._start_analysis)
        self.url_edit.textChanged.connect(self._invalidate_analysis_state)
        self.cookie_edit.textChanged.connect(self._invalidate_analysis_state)

    def _invalidate_analysis_state(self) -> None:
        if self.video_info is None:
            return
        self.video_info = None
        self._clear_format_tables()
        self.video_meta_label.setText("链接或 Cookie 已变化，请重新解析格式")
        self._set_format_count(0, 0, False)

    def _restore_settings(self) -> None:
        default_download = str(Path.home() / "Downloads")
        self.output_edit.setText(self.settings.value("download_dir", default_download, type=str))
        self.cookie_edit.setText(self.settings.value("cookie_file", "", type=str))
        geometry = self.settings.value("geometry_v22")
        if geometry is not None:
            self.restoreGeometry(geometry)

    def _save_settings(self) -> None:
        self.settings.setValue("download_dir", self.output_edit.text().strip())
        self.settings.setValue("cookie_file", self.cookie_edit.text().strip())
        self.settings.setValue("geometry_v22", self.saveGeometry())

    def _refresh_system_badges(self) -> None:
        self.snapshot = system_snapshot()
        self.ytdlp_badge.setText(f"yt-dlp  {self.snapshot.yt_dlp_version}")
        self.ytdlp_badge.setObjectName("StatusGood" if self.snapshot.yt_dlp_version != "未安装" else "StatusWarn")
        self.ffmpeg_badge.setText("FFmpeg  ✓" if self.snapshot.ffmpeg_ready else "FFmpeg  未检测到")
        self.ffmpeg_badge.setObjectName("StatusGood" if self.snapshot.ffmpeg_ready else "StatusWarn")

        runtime = self.snapshot.js_runtime
        if runtime and runtime.supported and self.snapshot.ejs_version:
            self.js_badge.setText(f"JS  {runtime.display_name} ✓")
            self.js_badge.setObjectName("StatusGood")
        elif runtime:
            self.js_badge.setText(f"JS  {runtime.display_name} ⚠")
            self.js_badge.setObjectName("StatusWarn")
        else:
            self.js_badge.setText("JS runtime  未检测")
            self.js_badge.setObjectName("StatusWarn")

        if runtime:
            ejs = self.snapshot.ejs_version or "未安装（启用 ejs:github 回退）"
            self.js_badge.setToolTip(
                f"Runtime: {runtime.display_name} {runtime.version}\n"
                f"Path: {runtime.path}\n"
                f"Supported: {'yes' if runtime.supported else 'no'}\n"
                f"yt-dlp-ejs: {ejs}\n"
                "Remote EJS fallback: ejs:github\n"
                "PO Token auto-fetch: disabled (不会启动浏览器 Provider)"
            )
        else:
            self.js_badge.setToolTip("未检测到支持的 JavaScript Runtime。推荐安装 Deno >= 2.3.0。")

        self.python_badge.setText(f"Python  {self.snapshot.python_version}")
        self.python_badge.setObjectName("StatusInfo")
        for badge in (self.ytdlp_badge, self.ffmpeg_badge, self.js_badge, self.python_badge):
            badge.style().unpolish(badge)
            badge.style().polish(badge)

    def _copy_diagnostics(self) -> None:
        snapshot = system_snapshot()
        text = "\n".join(
            [
                f"Neko Video Downloader: {__version__}",
                f"OS: {platform.platform()}",
                f"Python: {snapshot.python_version}",
                f"Python executable: {snapshot.executable}",
                f"yt-dlp: {snapshot.yt_dlp_version}",
                f"FFmpeg: {snapshot.ffmpeg_path or 'not found'}",
                f"ffprobe: {snapshot.ffprobe_path or 'not found'}",
                f"JavaScript runtime: {snapshot.javascript_runtime or 'not found'}",
                f"JavaScript runtime supported: {snapshot.js_runtime.supported if snapshot.js_runtime else False}",
                f"yt-dlp-ejs: {snapshot.ejs_version or 'not installed'}",
                "Remote EJS fallback: ejs:github",
                "PO Token provider auto-fetch: disabled (youtube:fetch_pot=never)",
            ]
        )
        QtWidgets.QApplication.clipboard().setText(text)
        self._log("success", "诊断信息已复制到剪贴板（不包含 URL、Cookie 内容或异常堆栈）。")

    def _clear_cookie(self) -> None:
        raw = self.cookie_edit.text().strip()
        if raw:
            try:
                clear_cookie_session(raw, root=self.cookie_store_dir)
                self._log("info", "已清除当前 Cookie 的应用工作会话；原始 cookies.txt 未被修改。")
            except BaseException as exc:
                self._show_error(classify_exception(exc, context="清除 Cookie 会话"))
                return
        self.cookie_edit.clear()

    def _choose_cookie(self) -> None:
        current = str(Path(self.cookie_edit.text()).parent) if self.cookie_edit.text().strip() else str(Path.home())
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "选择 Cookie 文件", current, "Cookie/Text Files (*.txt);;All Files (*)"
        )
        if path:
            self.cookie_edit.setText(path)

    def _choose_output(self) -> None:
        current = self.output_edit.text().strip() or str(Path.home())
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "选择下载目录", current)
        if path:
            self.output_edit.setText(path)

    def _open_output_folder(self) -> None:
        try:
            raw = self.output_edit.text().strip()
            if not raw:
                raise ValidationError("请先选择下载目录。")
            reveal_in_file_manager(Path(raw))
        except BaseException as exc:
            self._show_error(classify_exception(exc, context="打开下载目录"))

    def _set_analysis_busy(self, busy: bool) -> None:
        self.analyze_button.setEnabled(not busy)
        self.analyze_button.setText("正在解析…" if busy else "✦ 解析格式")
        self.download_button.setEnabled(not busy)
        self.update_button.setEnabled(not busy)
        self.update_channel.setEnabled(not busy)
        self.url_edit.setEnabled(not busy)
        self.cookie_edit.setEnabled(not busy)
        self.cookie_browse.setEnabled(not busy)
        self.cookie_clear.setEnabled(not busy)

    def _set_download_busy(self, busy: bool) -> None:
        enabled = not busy
        self.download_button.setEnabled(enabled)
        self.cancel_button.setEnabled(busy)
        self.analyze_button.setEnabled(enabled)
        self.update_button.setEnabled(enabled)
        self.update_channel.setEnabled(enabled)
        self.mode_combo.setEnabled(enabled)
        self.url_edit.setEnabled(enabled)
        self.cookie_edit.setEnabled(enabled)
        self.cookie_browse.setEnabled(enabled)
        self.cookie_clear.setEnabled(enabled)
        self.output_edit.setEnabled(enabled)
        self.output_browse.setEnabled(enabled)
        if enabled:
            self._apply_mode_state()
        else:
            self.video_table.setEnabled(False)
            self.audio_table.setEnabled(False)

    def _set_update_busy(self, busy: bool) -> None:
        enabled = not busy
        self.update_button.setEnabled(enabled)
        self.update_channel.setEnabled(enabled)
        self.analyze_button.setEnabled(enabled)
        self.download_button.setEnabled(enabled)

    def _start_analysis(self) -> None:
        if self.analyze_worker and self.analyze_worker.isRunning():
            return
        if (self.download_worker and self.download_worker.isRunning()) or (self.update_worker and self.update_worker.isRunning()):
            return
        try:
            url = validate_url(self.url_edit.text())
            cookie_path = validate_cookie_file(self.cookie_edit.text())
        except BaseException as exc:
            self._show_error(classify_exception(exc, context="解析视频"))
            return
        cookie = str(cookie_path) if cookie_path else ""
        self._clear_format_tables()
        self.video_info = None
        self.video_meta_label.setText("正在解析，请稍候…")
        self._set_format_count(0, 0, False)
        self._set_analysis_busy(True)
        self._log("info", "开始解析视频格式…")
        self.analyze_worker = AnalyzeWorker(url, cookie, self.cookie_store_dir, self)
        self.analyze_worker.log.connect(self._log)
        self.analyze_worker.succeeded.connect(self._analysis_succeeded)
        self.analyze_worker.failed.connect(self._analysis_failed)
        self.analyze_worker.finished.connect(lambda: self._set_analysis_busy(False))
        self.analyze_worker.start()

    def _analysis_succeeded(self, info: VideoInfo) -> None:
        self.video_info = info
        self.video_meta_label.setText(f"{info.title}  ·  {info.uploader}  ·  {info.duration_text}")
        self._populate_formats(info.formats, warning=bool(info.diagnostics))
        self._log("success", f"解析成功：{info.title}（{len(info.formats)} 个原始格式）")
        for diagnostic in info.diagnostics:
            self._log("warning", f"格式完整性：{diagnostic}")

    def _analysis_failed(self, error: UserFacingError) -> None:
        self.video_meta_label.setText("解析失败，请查看错误提示")
        self._show_error(error)

    def _clear_format_tables(self) -> None:
        self.video_table.setRowCount(0)
        self.audio_table.setRowCount(0)
        self.video_table.clearSelection()
        self.audio_table.clearSelection()
        self.video_count_label.setText("0")
        self.audio_count_label.setText("0")
        self.selection_summary.setText("当前选择：尚未选择格式")
        self.audio_hint_label.setText("可单独下载，或与左侧纯视频自动合并")

    def _set_format_count(self, video_count: int, audio_count: int, warning: bool) -> None:
        self.format_count_label.setText(f"视频 {video_count} · 音频 {audio_count}")
        self.format_count_label.setObjectName("StatusWarn" if warning else "StatusInfo")
        self.format_count_label.style().unpolish(self.format_count_label)
        self.format_count_label.style().polish(self.format_count_label)

    @staticmethod
    def _format_tooltip(fmt: FormatInfo) -> str:
        return (
            f"ID: {fmt.format_id}\n"
            f"类型: {fmt.stream_kind}\n"
            f"封装: {fmt.ext}\n"
            f"分辨率: {fmt.resolution}\n"
            f"FPS: {fmt.fps}\n"
            f"大小: {fmt.filesize}\n"
            f"码率: {fmt.tbr}\n"
            f"视频编码: {fmt.vcodec}\n"
            f"音频编码: {fmt.acodec}\n"
            f"协议: {fmt.protocol}\n"
            f"备注: {fmt.note or '—'}"
        )

    def _populate_table_row(self, table: QtWidgets.QTableWidget, row: int, fmt: FormatInfo, values: list[str]) -> None:
        tooltip = self._format_tooltip(fmt)
        for col, value in enumerate(values):
            item = QtWidgets.QTableWidgetItem(str(value))
            item.setTextAlignment(QtCore.Qt.AlignCenter)
            item.setToolTip(tooltip)
            if col == 0:
                item.setData(QtCore.Qt.UserRole, fmt)
            table.setItem(row, col, item)

    def _populate_formats(self, formats: tuple[FormatInfo, ...], *, warning: bool = False) -> None:
        video_formats = [fmt for fmt in formats if fmt.has_video]
        audio_formats = [fmt for fmt in formats if fmt.has_audio and not fmt.has_video]

        self.video_table.setSortingEnabled(False)
        self.audio_table.setSortingEnabled(False)
        self.video_table.setRowCount(len(video_formats))
        self.audio_table.setRowCount(len(audio_formats))

        for row, fmt in enumerate(video_formats):
            self._populate_table_row(
                self.video_table,
                row,
                fmt,
                [fmt.stream_kind, fmt.format_id, fmt.resolution, fmt.fps, fmt.ext, fmt.filesize, fmt.vcodec],
            )
        for row, fmt in enumerate(audio_formats):
            self._populate_table_row(
                self.audio_table,
                row,
                fmt,
                [fmt.format_id, fmt.ext, fmt.tbr, fmt.filesize, fmt.acodec],
            )

        self.video_table.setSortingEnabled(True)
        self.audio_table.setSortingEnabled(True)
        self.video_table.resizeRowsToContents()
        self.audio_table.resizeRowsToContents()
        self.video_count_label.setText(str(len(video_formats)))
        self.audio_count_label.setText(str(len(audio_formats)))
        self._set_format_count(len(video_formats), len(audio_formats), warning)
        self._update_selection_summary()

    @staticmethod
    def _selected_from_table(table: QtWidgets.QTableWidget) -> FormatInfo | None:
        rows = table.selectionModel().selectedRows() if table.selectionModel() else []
        if not rows:
            return None
        item = table.item(rows[0].row(), 0)
        fmt = item.data(QtCore.Qt.UserRole) if item else None
        return fmt if isinstance(fmt, FormatInfo) else None

    def _selected_formats(self) -> list[FormatInfo]:
        result: list[FormatInfo] = []
        video = self._selected_from_table(self.video_table)
        audio = self._selected_from_table(self.audio_table)
        if video:
            result.append(video)
        if audio:
            result.append(audio)
        return result

    def _on_video_selection_changed(self) -> None:
        video = self._selected_from_table(self.video_table)
        manual = self.mode_combo.currentData() == "manual"
        if video and video.has_audio:
            blocker = QtCore.QSignalBlocker(self.audio_table)
            self.audio_table.clearSelection()
            del blocker
            self.audio_table.setEnabled(False)
            self.audio_hint_label.setText("所选视频已包含音频，将作为单文件下载")
        else:
            self.audio_table.setEnabled(manual)
            self.audio_hint_label.setText("可单独下载，或与左侧纯视频自动合并")
        self._update_selection_summary()

    def _on_audio_selection_changed(self) -> None:
        self._update_selection_summary()

    def _update_selection_summary(self) -> None:
        video = self._selected_from_table(self.video_table)
        audio = self._selected_from_table(self.audio_table)
        if not video and not audio:
            text = "当前选择：尚未选择格式"
        elif video and video.has_audio:
            text = f"当前选择：音视频 {video.format_id} · 单文件直接下载"
        elif video and audio:
            text = f"当前选择：视频 {video.format_id} + 音频 {audio.format_id} · 下载后由 FFmpeg 自动合并"
        elif video:
            text = f"当前选择：视频 {video.format_id} · 仅下载视频轨道"
        else:
            text = f"当前选择：音频 {audio.format_id} · 仅下载音频轨道"
        self.selection_summary.setText(text)

    def _apply_mode_state(self) -> None:
        manual = self.mode_combo.currentData() == "manual"
        video = self._selected_from_table(self.video_table)
        self.video_table.setEnabled(manual)
        self.audio_table.setEnabled(manual and not (video and video.has_audio))
        if manual:
            self.video_table.setToolTip("左侧单选一个视频格式；纯视频可与右侧单选的音频格式自动合并。")
            self.audio_table.setToolTip("右侧单选一个纯音频格式；可单独下载，或与左侧纯视频合并。")
        else:
            tip = "当前使用智能下载模式，左右格式选择不会影响下载。"
            self.video_table.setToolTip(tip)
            self.audio_table.setToolTip(tip)

    def _build_download_request(self) -> DownloadRequest:
        url = validate_url(self.url_edit.text())
        output_dir = validate_output_dir(self.output_edit.text())
        cookie_path = validate_cookie_file(self.cookie_edit.text())
        mode = str(self.mode_combo.currentData())
        if mode == "manual":
            selector, needs_merge = select_manual_format(self._selected_formats())
        else:
            selector, needs_merge = selector_for_mode(mode, ffmpeg_ready=self.snapshot.ffmpeg_ready)
        if needs_merge and not self.snapshot.ffmpeg_ready:
            raise ValidationError("当前选择需要合并音视频，但没有检测到 ffmpeg/ffprobe。")
        return DownloadRequest(url, output_dir, cookie_path, selector, needs_merge)

    def _start_download(self) -> None:
        if self.download_worker and self.download_worker.isRunning():
            return
        if (self.analyze_worker and self.analyze_worker.isRunning()) or (self.update_worker and self.update_worker.isRunning()):
            return
        try:
            request = self._build_download_request()
        except BaseException as exc:
            error = classify_exception(exc, context="创建下载任务")
            if "ffmpeg" in str(exc).lower():
                error = UserFacingError(
                    "E_FFMPEG_MISSING",
                    "需要 FFmpeg/ffprobe",
                    "你选择了需要合并的纯视频 + 纯音频格式，但系统未检测到 FFmpeg。",
                    str(exc),
                    ("安装 FFmpeg 并确保 ffmpeg/ffprobe 在 PATH 中。", "或选择左侧已包含音频的单文件格式。"),
                )
            self._show_error(error)
            return

        self._save_settings()
        self._set_download_busy(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("正在初始化…")
        self.progress_detail.setText("速度 —  ·  ETA —")
        self._log("info", f"开始下载，格式：{request.format_selector}")
        self.download_worker = DownloadWorker(request, self.cookie_store_dir, self)
        self.download_worker.log.connect(self._log)
        self.download_worker.progress.connect(self._download_progress)
        self.download_worker.succeeded.connect(self._download_succeeded)
        self.download_worker.cancelled.connect(self._download_cancelled)
        self.download_worker.failed.connect(self._download_failed)
        self.download_worker.finished.connect(self._download_finished)
        self.download_worker.start()

    def _download_progress(self, progress: ProgressInfo) -> None:
        if progress.percent is None:
            self.progress_bar.setRange(0, 0)
            self.progress_bar.setFormat(progress.status_text)
        else:
            if self.progress_bar.maximum() == 0:
                self.progress_bar.setRange(0, 100)
            value = int(progress.percent)
            self.progress_bar.setValue(value)
            self.progress_bar.setFormat(f"{progress.status_text}  {progress.percent:.1f}%")
        speed = progress.speed or "—"
        eta = progress.eta or "—"
        self.progress_detail.setText(f"速度 {speed}  ·  ETA {eta}")

    def _download_succeeded(self, message: str) -> None:
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.progress_bar.setFormat("下载完成 ♡")
        self._log("success", message)
        QtWidgets.QMessageBox.information(self, "下载完成", "下载任务已完成。\n\n可以点击“打开目录”查看文件。")

    def _download_cancelled(self, message: str) -> None:
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("已取消")
        self._log("warning", message)

    def _download_failed(self, error: UserFacingError) -> None:
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("下载失败")
        self._show_error(error)

    def _download_finished(self) -> None:
        self._set_download_busy(False)
        if self._close_after_download:
            self._close_after_download = False
            QtCore.QTimer.singleShot(0, self.close)

    def _cancel_download(self) -> None:
        if self.download_worker and self.download_worker.isRunning():
            self.cancel_button.setEnabled(False)
            self.progress_bar.setFormat("正在取消…")
            self._log("warning", "已发送取消请求；将在当前下载回调点安全停止。")
            self.download_worker.cancel()

    def _start_update(self) -> None:
        if self.update_worker and self.update_worker.isRunning():
            return
        if (self.analyze_worker and self.analyze_worker.isRunning()) or (self.download_worker and self.download_worker.isRunning()):
            return
        channel = str(self.update_channel.currentData())
        self._set_update_busy(True)
        self.update_button.setText("正在更新…")
        self._log("info", f"开始更新 yt-dlp（{channel}）…")
        self.update_worker = UpdateWorker(channel, self)
        self.update_worker.output.connect(lambda text: self._log("update", text))
        self.update_worker.succeeded.connect(self._update_succeeded)
        self.update_worker.failed.connect(self._update_failed)
        self.update_worker.finished.connect(self._update_finished)
        self.update_worker.start()

    def _update_succeeded(self, old_version: str, new_version: str) -> None:
        self._refresh_system_badges()
        self._log("success", f"yt-dlp 更新完成：{old_version} → {new_version}")
        QtWidgets.QMessageBox.information(
            self,
            "yt-dlp 更新完成",
            f"更新成功：{old_version} → {new_version}\n\n同时会同步 yt-dlp[default] 依赖（包括 yt-dlp-ejs）。为了确保已导入模块完全刷新，建议重启本应用后再继续解析/下载。",
        )

    def _update_failed(self, error: UserFacingError) -> None:
        self._show_error(error)

    def _update_finished(self) -> None:
        self._set_update_busy(False)
        self.update_button.setText("↻ 一键更新 yt-dlp")

    def _show_error(self, error: UserFacingError) -> None:
        self._log("error", f"[{error.code}] {error.title}：{error.message}")
        box = QtWidgets.QMessageBox(self)
        box.setIcon(QtWidgets.QMessageBox.Critical)
        box.setWindowTitle(f"{error.title} · {error.code}")
        box.setText(error.message)
        informative = f"错误代码：{error.code}"
        if error.suggestions:
            informative += "\n\n建议：\n" + "\n".join(f"• {item}" for item in error.suggestions)
        box.setInformativeText(informative)
        box.exec_()

    @QtCore.pyqtSlot(str, str)
    def _log(self, level: str, message: str) -> None:
        if not message:
            return
        prefix = {
            "success": "✓",
            "warning": "!",
            "error": "×",
            "update": "↻",
            "debug": "·",
        }.get(level, "•")
        stamp = datetime.now().strftime("%H:%M:%S")
        for line in str(message).splitlines() or [""]:
            self.log_edit.appendPlainText(f"[{stamp}] {prefix} {line}")
        scrollbar = self.log_edit.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self._save_settings()
        if self.update_worker and self.update_worker.isRunning():
            QtWidgets.QMessageBox.warning(self, "更新进行中", "yt-dlp 正在更新。为避免破坏当前 Python 环境，请等待更新结束后再关闭程序。")
            event.ignore()
            return
        if self.analyze_worker and self.analyze_worker.isRunning():
            QtWidgets.QMessageBox.information(self, "解析进行中", "视频格式仍在解析，请在解析结束后关闭程序。")
            event.ignore()
            return
        if self.download_worker and self.download_worker.isRunning():
            reply = QtWidgets.QMessageBox.question(
                self,
                "下载仍在进行",
                "关闭前需要先取消当前下载。是否发送取消请求并在任务安全停止后自动关闭？",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No,
            )
            if reply == QtWidgets.QMessageBox.Yes:
                self._close_after_download = True
                self.download_worker.cancel()
            event.ignore()
            return
        super().closeEvent(event)
