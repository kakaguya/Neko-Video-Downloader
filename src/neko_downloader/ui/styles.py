APP_QSS = r"""
QMainWindow, QWidget#Root {
    background: #171321;
    color: #f7eefc;
    font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
    font-size: 10pt;
}

QFrame#HeaderCard {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                stop:0 #2b1d3a, stop:0.45 #342044, stop:1 #1f2a46);
    border: 1px solid #5b3f70;
    border-radius: 18px;
}

QFrame#Card {
    background: #211a2d;
    border: 1px solid #41334f;
    border-radius: 14px;
}

/*
主窗口普通 QLabel。
不要使用全局 QLabel，否则 QMessageBox 等浅色系统弹窗
也会继承浅色字体，导致正文无法看清。
*/
QWidget#Root QLabel {
    color: #eadff0;
}

QLabel#AppTitle {
    color: #fff5ff;
    font-size: 22pt;
    font-weight: 800;
}

QLabel#FieldLabel {
    color: #ead8f3;
    font-weight: 700;
    padding: 0 4px 0 2px;
}

QLabel#SectionTitle {
    color: #f7d7ff;
    font-size: 12pt;
    font-weight: 700;
}


/* =========================
   格式选择区域
   ========================= */

QFrame#FormatPanel {
    background: #191421;
    border: 1px solid #3e3150;
    border-radius: 11px;
}

QLabel#FormatTitle {
    color: #ffd8ef;
    font-size: 11pt;
    font-weight: 800;
}

QLabel#PanelHint {
    color: #b8a8c4;
    font-size: 8.8pt;
}

QLabel#MiniBadge {
    background: #342641;
    color: #efceff;
    border: 1px solid #5d4370;
    border-radius: 8px;
    padding: 2px 7px;
    font-weight: 700;
}

QLabel#SelectionSummary {
    background: #271d33;
    color: #f5d9ff;
    border: 1px solid #503d61;
    border-radius: 9px;
    padding: 7px 10px;
    font-weight: 700;
}

QLabel#Hint {
    color: #a99ab4;
    font-size: 9pt;
}


/* =========================
   状态徽章
   ========================= */

QLabel#StatusGood {
    background: #17372f;
    color: #9ef0cd;
    border: 1px solid #2d6b59;
    border-radius: 10px;
    padding: 4px 9px;
    font-weight: 700;
}

QLabel#StatusWarn {
    background: #3b2c19;
    color: #ffd79a;
    border: 1px solid #76572b;
    border-radius: 10px;
    padding: 4px 9px;
    font-weight: 700;
}

QLabel#StatusInfo {
    background: #2e2340;
    color: #e8c9ff;
    border: 1px solid #60447e;
    border-radius: 10px;
    padding: 4px 9px;
    font-weight: 700;
}


/* =========================
   输入框 / 下拉框
   ========================= */

QLineEdit, QComboBox {
    background: #17131f;
    color: #f8f1fb;
    border: 1px solid #51405e;
    border-radius: 9px;
    padding: 8px 10px;
    min-height: 20px;
    selection-background-color: #d979b9;
}

QLineEdit:focus, QComboBox:focus {
    border: 1px solid #f091c8;
}

QLineEdit:disabled, QComboBox:disabled {
    color: #766d7c;
    background: #1b1820;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox QAbstractItemView {
    background: #211a2d;
    border: 1px solid #5f4870;
    selection-background-color: #754c7a;
    color: #f8f1fb;
}


/* =========================
   按钮
   ========================= */

QPushButton {
    background: #3a2b48;
    color: #f9efff;
    border: 1px solid #654d75;
    border-radius: 9px;
    padding: 8px 14px;
    font-weight: 700;
}

QPushButton:hover {
    background: #4b365c;
    border-color: #a86eb0;
}

QPushButton:pressed {
    background: #2c2036;
}

QPushButton:disabled {
    color: #756b7b;
    background: #242027;
    border-color: #37313c;
}

QPushButton#PrimaryButton {
    background: qlineargradient(
        x1:0, y1:0,
        x2:1, y2:0,
        stop:0 #df73b2,
        stop:1 #9c78df
    );
    color: #1c1324;
    border: none;
    padding: 10px 18px;
}

QPushButton#PrimaryButton:hover {
    background: qlineargradient(
        x1:0, y1:0,
        x2:1, y2:0,
        stop:0 #f08ac5,
        stop:1 #b491f0
    );
}

QPushButton#AccentButton {
    background: #29465a;
    color: #c9f3ff;
    border-color: #3f718d;
}

QPushButton#DangerButton {
    background: #4a2738;
    color: #ffcbdb;
    border-color: #81435f;
}


/* =========================
   表格
   ========================= */

QTableWidget {
    background: #17131f;
    alternate-background-color: #1d1726;
    color: #efe6f4;
    border: 1px solid #44354f;
    border-radius: 10px;
    gridline-color: #30263a;
    selection-background-color: #67456f;
    selection-color: #ffffff;
    outline: 0;
}

QHeaderView::section {
    background: #2d2337;
    color: #f5dffb;
    border: none;
    border-right: 1px solid #44354f;
    border-bottom: 1px solid #44354f;
    padding: 7px;
    font-weight: 700;
}

QTableCornerButton::section {
    background: #2d2337;
    border: none;
}


/* =========================
   运行状态
   ========================= */

QPlainTextEdit {
    background: #120f18;
    color: #d9f2e6;
    border: 1px solid #3e3347;
    border-radius: 10px;
    padding: 8px;
    font-family: "JetBrains Mono", "Cascadia Mono", "Consolas", monospace;
    font-size: 9pt;
}


/* =========================
   进度条
   ========================= */

QProgressBar {
    background: #17131f;
    color: #fff;
    border: 1px solid #493852;
    border-radius: 8px;
    text-align: center;
    min-height: 16px;
}

QProgressBar::chunk {
    border-radius: 7px;
    background: qlineargradient(
        x1:0, y1:0,
        x2:1, y2:0,
        stop:0 #ef84c1,
        stop:1 #7fcfea
    );
}


/* =========================
   滚动条
   ========================= */

QScrollBar:vertical {
    background: #17131f;
    width: 10px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: #4a3a56;
    border-radius: 5px;
    min-height: 28px;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0;
}


/* =========================
   状态栏
   ========================= */

QStatusBar {
    color: #ac9ab5;
    background: #171321;
}


/* =========================
   Tooltip
   ========================= */

QToolTip {
    background: #2b2035;
    color: #ffffff;
    border: 1px solid #7c5b89;
    padding: 5px;
}


/* =========================
   QMessageBox
   ========================= */

/*
QMessageBox 通常使用 Windows / Fusion 的浅色弹窗背景。

必须单独指定文字为深色，否则主界面的浅色 QLabel
规则可能使“下载完成”“错误提示”“更新完成”等弹窗
正文几乎无法看清。
*/
QMessageBox {
    background-color: #f4f4f4;
}

QMessageBox QLabel {
    color: #111111;
}

/*
按钮继续保留 Neko 的紫色风格。
这里显式写一次，避免部分 Qt/Windows 环境下
QMessageBox 按钮使用系统默认颜色。
*/
QMessageBox QPushButton {
    background: #3a2b48;
    color: #ffffff;
    border: 1px solid #654d75;
    border-radius: 9px;
    padding: 7px 16px;
    min-width: 44px;
    min-height: 22px;
    font-weight: 700;
}

QMessageBox QPushButton:hover {
    background: #4b365c;
    border-color: #a86eb0;
}

QMessageBox QPushButton:pressed {
    background: #2c2036;
}
"""


# =========================
# 小尺寸窗口滚动安全
# =========================
#
# 当程序在非最大化窗口运行时，让主页面使用滚动，
# 而不是继续压缩按钮、标签等控件导致文字被裁切。
APP_QSS += r"""
QScrollArea#MainScroll {
    border: none;
    background: #171321;
}

QScrollArea#MainScroll QWidget#qt_scrollarea_viewport {
    background: #171321;
}

QPushButton,
QLineEdit,
QComboBox {
    min-height: 20px;
}
"""