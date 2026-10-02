"""분할/병합 결과를 저장하기 전에 썸네일로 확인하는 화면."""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.pdf_merger import MergePlan
from core.pdf_splitter import SplitPlan
from ui.widgets import ThumbnailTile, ThumbnailWorker, create_button, create_card


class PreviewPage(QWidget):
    """결과 파일별 썸네일. 수정은 입력 화면으로, 확인은 저장 화면으로 보낸다."""

    edit_requested = pyqtSignal(str)
    confirm_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("contentPage")
        self._origin = "split"
        self._generation = 0
        self._worker: ThumbnailWorker | None = None
        self._tiles: list[ThumbnailTile] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 32, 36, 28)
        root.setSpacing(8)

        self._title = QLabel("미리보기")
        self._title.setObjectName("pageTitle")
        self._description = QLabel("결과를 확인한 뒤 저장하거나, 입력 화면으로 돌아가 수정합니다.")
        self._description.setObjectName("pageHint")
        self._description.setWordWrap(True)
        self._banner = QLabel("")
        self._banner.setObjectName("errorLabel")
        self._banner.setWordWrap(True)

        root.addWidget(self._title)
        root.addWidget(self._description)
        root.addWidget(self._banner)
        root.addSpacing(8)

        self._scroll = QScrollArea()
        self._scroll.setObjectName("pageScroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._body = QWidget()
        self._body.setObjectName("contentPage")
        self._body.setAttribute(Qt.WA_StyledBackground, True)
        self._body_layout = QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(0, 0, 8, 0)
        self._body_layout.setSpacing(16)
        self._body_layout.addStretch(1)
        self._scroll.setWidget(self._body)
        root.addWidget(self._scroll, 1)

        actions = QHBoxLayout()
        edit = create_button("수정", "secondaryButton")
        edit.setMinimumWidth(120)
        edit.clicked.connect(self._edit)
        confirm = create_button("확인", "primaryButton")
        confirm.setMinimumWidth(120)
        confirm.clicked.connect(self.confirm_requested.emit)
        actions.addWidget(edit)
        actions.addStretch(1)
        actions.addWidget(confirm)
        root.addSpacing(8)
        root.addLayout(actions)

    def show_split(self, plan: SplitPlan) -> None:
        """분할 결과 파일마다 썸네일 묶음을 만든다."""
        self._origin = "split"
        self._title.setText("분할 미리보기")
        self._description.setText(
            f"{plan.source_name}  ·  총 {plan.page_count}페이지  ·  결과 {len(plan.groups)}개 파일"
        )
        groups: list[tuple[str, list[tuple[str, int, str]]]] = []
        for index, (group, label) in enumerate(zip(plan.groups, plan.labels), start=1):
            pages = [(plan.source_path, page, str(page + 1)) for page in group]
            groups.append((f"파일 {index}  ·  {label}  ·  {len(group)}페이지", pages))
        self._show_groups(groups)

    def show_merge(self, plan: MergePlan) -> None:
        """병합 순서대로 파일별 썸네일을 이어 보여 준다."""
        self._origin = "merge"
        names = "   ·   ".join(item.name for item in plan.items)
        self._title.setText("병합 미리보기")
        self._description.setText(f"{len(plan.items)}개 파일  ·  총 {plan.total_pages}페이지  ·  {names}")
        groups = []
        output_page = 1
        for index, item in enumerate(plan.items, start=1):
            pages = []
            for page in range(item.page_count):
                pages.append((item.path, page, str(output_page)))
                output_page += 1
            groups.append((f"{index}.  {item.name}  ·  {item.page_count}페이지", pages))
        self._show_groups(groups)

    def shutdown(self) -> None:
        """창을 닫기 전에 썸네일 작업을 멈춘다."""
        worker = self._worker
        self._worker = None
        if worker is None:
            return
        worker.blockSignals(True)
        worker.requestInterruption()
        if worker.isRunning():
            worker.wait(3000)
        worker.deleteLater()

    def _edit(self) -> None:
        self.edit_requested.emit(self._origin)

    def _show_groups(self, groups: list[tuple[str, list[tuple[str, int, str]]]]) -> None:
        self._banner.setText("")
        self._stop_worker()
        self._clear_body()
        self._tiles = []
        tasks: list[tuple[int, str, int]] = []

        for title, pages in groups:
            card, layout = create_card()
            heading = QLabel(title)
            heading.setObjectName("groupTitle")
            heading.setWordWrap(True)
            layout.addWidget(heading)

            grid_host = QWidget()
            grid = QGridLayout(grid_host)
            grid.setContentsMargins(0, 8, 0, 0)
            grid.setHorizontalSpacing(16)
            grid.setVerticalSpacing(16)
            columns = 4
            for position, (path, index, caption) in enumerate(pages):
                tile = ThumbnailTile(caption)
                self._tiles.append(tile)
                tasks.append((len(self._tiles) - 1, path, index))
                grid.addWidget(tile, position // columns, position % columns)
            layout.addWidget(grid_host)
            self._body_layout.insertWidget(self._body_layout.count() - 1, card)

        if not tasks:
            self._banner.setText("미리볼 페이지가 없습니다.")
            return

        self._generation += 1
        generation = self._generation
        worker = ThumbnailWorker(tasks, self)
        worker.ready.connect(lambda tile, data, token=generation: self._on_ready(token, tile, data))
        worker.failed.connect(lambda tile, message, token=generation: self._on_failed(token, tile, message))
        worker.group_failed.connect(lambda message, token=generation: self._on_group_failed(token, message))
        self._worker = worker
        worker.start()
        self._scroll.verticalScrollBar().setValue(0)

    def _on_ready(self, generation: int, tile_id: int, data: bytes) -> None:
        if generation != self._generation or tile_id >= len(self._tiles):
            return
        self._tiles[tile_id].set_png(data)

    def _on_failed(self, generation: int, tile_id: int, message: str) -> None:
        if generation != self._generation or tile_id >= len(self._tiles):
            return
        self._tiles[tile_id].set_failed(message)

    def _on_group_failed(self, generation: int, message: str) -> None:
        if generation != self._generation:
            return
        self._banner.setText(message)

    def _stop_worker(self) -> None:
        worker = self._worker
        self._worker = None
        if worker is None:
            return
        worker.blockSignals(True)
        worker.requestInterruption()
        worker.finished.connect(worker.deleteLater)

    def _clear_body(self) -> None:
        while self._body_layout.count() > 1:
            item = self._body_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
