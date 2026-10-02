"""여러 화면에서 같이 쓰는 버튼, 카드, 썸네일."""

from PyQt5.QtCore import QSize, Qt, QThread, pyqtSignal
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.thumbnail import ThumbnailError, render_pages
from ui.styles import icon_path


def create_button(text: str, object_name: str, icon_name: str | None = None) -> QPushButton:
    """채움 버튼 또는 외곽선 버튼에 아이콘을 붙인다."""
    button = QPushButton(text)
    button.setObjectName(object_name)
    button.setCursor(Qt.PointingHandCursor)
    button.setMinimumHeight(36)
    if icon_name:
        path = icon_path(icon_name)
        if path.exists():
            button.setIcon(QIcon(str(path)))
            button.setIconSize(QSize(16, 16))
    return button


def create_card() -> tuple[QFrame, QVBoxLayout]:
    """흰 배경의 구역 카드를 만든다."""
    card = QFrame()
    card.setObjectName("card")
    card.setAttribute(Qt.WA_StyledBackground, True)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(24, 20, 24, 20)
    layout.setSpacing(10)
    return card, layout


def section_label(text: str) -> QLabel:
    """카드 안의 소제목."""
    label = QLabel(text)
    label.setObjectName("sectionTitle")
    return label


def error_label() -> QLabel:
    """입력 오류를 카드 안에 빨간 글씨로 보여 주는 라벨."""
    label = QLabel("")
    label.setObjectName("errorLabel")
    label.setWordWrap(True)
    label.setMinimumHeight(18)
    return label


class ThumbnailTile(QFrame):
    """페이지 번호와 미리보기 이미지를 담는 칸."""

    def __init__(self, caption: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("thumbTile")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._image = QLabel("불러오는 중")
        self._image.setObjectName("thumbImage")
        self._image.setAlignment(Qt.AlignCenter)
        self._image.setFixedSize(112, 148)
        self._image.setWordWrap(True)

        caption_label = QLabel(caption)
        caption_label.setObjectName("thumbCaption")
        caption_label.setAlignment(Qt.AlignCenter)

        layout.addWidget(self._image)
        layout.addWidget(caption_label)

    def set_png(self, data: bytes) -> None:
        """PNG 바이트를 칸 크기에 맞춰 표시한다."""
        pixmap = QPixmap()
        if not pixmap.loadFromData(data, "PNG"):
            self.set_failed("이미지를 읽지 못했습니다.")
            return
        scaled = pixmap.scaled(112, 148, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._image.setPixmap(scaled)
        self._image.setText("")

    def set_failed(self, message: str) -> None:
        """이 페이지만 실패했을 때 칸 안에 짧은 안내를 남긴다."""
        self._image.setPixmap(QPixmap())
        self._image.setText("표시 불가")
        self.setToolTip(message)


class ThumbnailWorker(QThread):
    """썸네일을 만든 뒤 타일 번호와 PNG를 메인 스레드로 보낸다."""

    ready = pyqtSignal(int, bytes)
    failed = pyqtSignal(int, str)
    group_failed = pyqtSignal(str)

    def __init__(self, tasks: list[tuple[int, str, int]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tasks = tasks

    def run(self) -> None:
        """같은 파일은 한 번만 열어 요청 순서와 상관없이 타일에 결과를 돌려준다."""
        grouped: dict[str, list[tuple[int, int]]] = {}
        order: list[str] = []
        for tile_id, path, index in self._tasks:
            if path not in grouped:
                order.append(path)
                grouped[path] = []
            grouped[path].append((tile_id, index))

        try:
            for path in order:
                if self.isInterruptionRequested():
                    return
                pairs = grouped[path]
                try:
                    rendered = render_pages(path, [index for _, index in pairs])
                except ThumbnailError as exc:
                    message = str(exc)
                    for tile_id, _index in pairs:
                        self.failed.emit(tile_id, message)
                    continue
                for (tile_id, _index), data in zip(pairs, rendered):
                    if self.isInterruptionRequested():
                        return
                    if data is None:
                        self.failed.emit(tile_id, "이 페이지를 표시하지 못했습니다.")
                    else:
                        self.ready.emit(tile_id, data)
        except Exception as exc:
            self.group_failed.emit(f"미리보기를 만들지 못했습니다. {exc}")
