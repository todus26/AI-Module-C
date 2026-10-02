"""아이콘 버튼과 포맷 표."""

from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import QSize, Qt
from PyQt5.QtGui import QColor, QIcon, QImage, QPainter, QPixmap
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtWidgets import QHeaderView, QPushButton, QTableWidget, QTableWidgetItem

from core.analyzer import FormatOption
from ui.styles import DISABLED_TEXT, PRIMARY_LIGHT

_COLUMNS = ("종류", "해상도", "확장자", "FPS", "코덱", "예상 용량")


def load_icon(filename: str, color: str, disabled_color: str = DISABLED_TEXT) -> QIcon:
    """SVG를 단색으로 칠해 QIcon으로 만든다."""
    path = str(Path(__file__).resolve().parents[1] / "resources" / "icons" / filename)
    renderer = QSvgRenderer(path)
    if not renderer.isValid():
        return QIcon()

    icon = QIcon()
    tints = (
        (QIcon.Normal, color),
        (QIcon.Active, color),
        (QIcon.Selected, color),
        (QIcon.Disabled, disabled_color),
    )
    for mode, tint in tints:
        image = QImage(32, 32, QImage.Format_ARGB32)
        image.fill(Qt.transparent)
        painter = QPainter(image)
        try:
            painter.setRenderHint(QPainter.Antialiasing, True)
            renderer.render(painter)
            painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
            painter.fillRect(image.rect(), QColor(tint))
        finally:
            painter.end()
        pixmap = QPixmap.fromImage(image)
        pixmap.setDevicePixelRatio(2)
        icon.addPixmap(pixmap, mode, QIcon.Off)
    return icon


class IconButton(QPushButton):
    """글자 없이 아이콘만 보여주는 정사각 버튼."""

    def __init__(self, icon: QIcon, tooltip: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("refreshButton")
        self.setIcon(icon)
        self.setIconSize(QSize(16, 16))
        self.setToolTip(tooltip)
        self.setAccessibleName(tooltip)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(32, 32)


class FormatTable(QTableWidget):
    """단일 선택 포맷 목록."""

    def __init__(self, parent=None) -> None:
        super().__init__(0, len(_COLUMNS), parent)
        self.setObjectName("formatTable")
        self.setHorizontalHeaderLabels(list(_COLUMNS))
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setSelectionMode(QTableWidget.SingleSelection)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setShowGrid(False)
        self.setAlternatingRowColors(False)
        self.setWordWrap(False)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(44)
        self.horizontalHeader().setHighlightSections(False)
        self.horizontalHeader().setStretchLastSection(False)
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for column in range(1, len(_COLUMNS)):
            self.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeToContents)
        self.setHorizontalScrollMode(QTableWidget.ScrollPerPixel)
        self.setVerticalScrollMode(QTableWidget.ScrollPerPixel)

    def set_formats(self, formats: list[FormatOption]) -> None:
        """포맷 목록을 표에 다시 채운다."""
        self.blockSignals(True)
        self.clearSelection()
        self.setRowCount(0)
        for option in formats:
            self._append_row(option)
        self.blockSignals(False)

    def clear_formats(self) -> None:
        """선택과 행을 모두 지운다."""
        self.blockSignals(True)
        self.clearSelection()
        self.setRowCount(0)
        self.blockSignals(False)

    def selected_format(self) -> FormatOption | None:
        """현재 선택된, 받을 수 있는 포맷을 반환한다."""
        row = self.currentRow()
        if row < 0:
            return None
        item = self.item(row, 0)
        if item is None:
            return None
        option = item.data(Qt.UserRole)
        if not isinstance(option, FormatOption) or not option.enabled:
            return None
        return option

    def _append_row(self, option: FormatOption) -> None:
        row = self.rowCount()
        self.insertRow(row)
        values = (
            option.kind_label,
            option.resolution_label,
            option.ext,
            option.fps_label,
            option.codec_label,
            option.filesize_label,
        )
        for column, value in enumerate(values):
            item = QTableWidgetItem(value)
            item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            flags = Qt.ItemIsEnabled
            if option.enabled:
                flags |= Qt.ItemIsSelectable
            item.setFlags(flags)
            if option.is_preset and option.enabled:
                item.setBackground(QColor(PRIMARY_LIGHT))
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            if not option.enabled:
                item.setForeground(QColor(DISABLED_TEXT))
                if option.disabled_reason:
                    item.setToolTip(option.disabled_reason)
            if column == 0:
                item.setData(Qt.UserRole, option)
            self.setItem(row, column, item)
