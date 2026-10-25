from __future__ import annotations

import sys
from pathlib import Path

from PyQt5 import QtCore, QtGui, QtWidgets

from .ui.main_window import MainWindow
from .ui.styles import APP_QSS


def _create_app_icon() -> QtGui.QIcon:
    size = 128
    pixmap = QtGui.QPixmap(size, size)
    pixmap.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)

    face = QtGui.QPainterPath()
    face.addRoundedRect(QtCore.QRectF(23, 33, 82, 72), 28, 28)
    painter.fillPath(face, QtGui.QColor("#f3a6d0"))

    ears = QtGui.QPainterPath()
    ears.moveTo(30, 48)
    ears.lineTo(39, 18)
    ears.lineTo(59, 39)
    ears.closeSubpath()
    ears.moveTo(98, 48)
    ears.lineTo(89, 18)
    ears.lineTo(69, 39)
    ears.closeSubpath()
    painter.fillPath(ears, QtGui.QColor("#f3a6d0"))

    inner = QtGui.QPainterPath()
    inner.moveTo(38, 38)
    inner.lineTo(42, 27)
    inner.lineTo(50, 38)
    inner.closeSubpath()
    inner.moveTo(90, 38)
    inner.lineTo(86, 27)
    inner.lineTo(78, 38)
    inner.closeSubpath()
    painter.fillPath(inner, QtGui.QColor("#b77ad6"))

    painter.setBrush(QtGui.QColor("#382641"))
    painter.setPen(QtCore.Qt.NoPen)
    painter.drawEllipse(QtCore.QPointF(49, 67), 5, 7)
    painter.drawEllipse(QtCore.QPointF(79, 67), 5, 7)
    painter.setBrush(QtGui.QColor("#ffffff"))
    painter.drawEllipse(QtCore.QPointF(50.5, 64.5), 1.7, 2.2)
    painter.drawEllipse(QtCore.QPointF(80.5, 64.5), 1.7, 2.2)

    pen = QtGui.QPen(QtGui.QColor("#51324c"), 4, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap)
    painter.setPen(pen)
    painter.drawArc(QtCore.QRectF(56, 73, 16, 12), 200 * 16, 140 * 16)
    painter.end()
    return QtGui.QIcon(pixmap)


def _app_data_dir() -> Path:
    base = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.AppDataLocation)
    if not base:
        base = str(Path.home() / ".neko-video-downloader")
    path = Path(base)
    path.mkdir(parents=True, exist_ok=True)
    return path


def main() -> int:
    if hasattr(QtCore.Qt, "AA_EnableHighDpiScaling"):
        QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    if hasattr(QtCore.Qt, "AA_UseHighDpiPixmaps"):
        QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)

    QtCore.QCoreApplication.setOrganizationName("NekoDownloader")
    QtCore.QCoreApplication.setApplicationName("NekoVideoDownloader")
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(APP_QSS)
    icon = _create_app_icon()
    app.setWindowIcon(icon)

    window = MainWindow(_app_data_dir())
    window.setWindowIcon(icon)
    window.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
