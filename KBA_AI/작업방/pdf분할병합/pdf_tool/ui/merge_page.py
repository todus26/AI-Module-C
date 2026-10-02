"""여러 PDF를 고르고 순서를 바꾼 뒤 병합을 요청하는 화면."""

from pathlib import Path

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.pdf_merger import MergeItem, MergePlan, build_merge_plan
from core.pdf_splitter import PdfDocumentError, inspect_pdf
from ui.widgets import create_button, create_card, error_label, section_label

_PATH_ROLE = Qt.UserRole
_COUNT_ROLE = Qt.UserRole + 1
_NAME_ROLE = Qt.UserRole + 2


class ReorderList(QListWidget):
    """드래그로 순서를 바꿀 때 항목이 복사되지 않게 이동만 허용한다."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setMinimumHeight(180)

    def dropEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        event.setDropAction(Qt.MoveAction)
        super().dropEvent(event)


class MergePage(QWidget):
    """병합 입력 화면. 목록과 순서는 수정으로 돌아와도 그대로다."""

    merge_requested = pyqtSignal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("contentPage")
        self._directory = str(Path.home())

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 32, 36, 28)
        root.setSpacing(8)

        title = QLabel("병합")
        title.setObjectName("pageTitle")
        description = QLabel("PDF를 여러 개 고른 뒤 순서를 정합니다. 같은 파일도 다시 추가할 수 있습니다.")
        description.setObjectName("pageHint")
        description.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(description)
        root.addSpacing(12)

        card, layout = create_card()
        header = QHBoxLayout()
        header.addWidget(section_label("파일 목록"))
        header.addStretch(1)
        choose = create_button("파일 선택", "secondaryButton", "upload.svg")
        choose.clicked.connect(self._choose_files)
        header.addWidget(choose)
        layout.addLayout(header)

        self._summary = QLabel("선택된 파일 없음")
        self._summary.setObjectName("pageHint")
        layout.addWidget(self._summary)

        self._list = ReorderList()
        self._list.currentRowChanged.connect(lambda _row: self._sync_buttons())
        model = self._list.model()
        model.rowsInserted.connect(lambda *_args: self._refresh_summary())
        model.rowsRemoved.connect(lambda *_args: self._refresh_summary())
        model.rowsMoved.connect(lambda *_args: self._refresh_summary())
        layout.addWidget(self._list)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self._up = create_button("위로", "secondaryButton", "up.svg")
        self._down = create_button("아래로", "secondaryButton", "down.svg")
        self._delete = create_button("삭제", "secondaryButton", "delete.svg")
        self._up.clicked.connect(self._move_up)
        self._down.clicked.connect(self._move_down)
        self._delete.clicked.connect(self._delete_current)
        actions.addWidget(self._up)
        actions.addWidget(self._down)
        actions.addWidget(self._delete)
        actions.addStretch(1)
        layout.addLayout(actions)

        self._error = error_label()
        layout.addWidget(self._error)
        root.addWidget(card, 1)

        action_row = QHBoxLayout()
        action_row.addStretch(1)
        merge = create_button("병합", "primaryButton", "merge_white.svg")
        merge.setMinimumWidth(120)
        merge.clicked.connect(self._submit)
        action_row.addWidget(merge)
        root.addSpacing(8)
        root.addLayout(action_row)
        self._sync_buttons()

    def _choose_files(self) -> None:
        """한 번에 여러 PDF를 고른다. 이미 있는 파일도 다시 넣을 수 있다."""
        paths, _selected = QFileDialog.getOpenFileNames(
            self,
            "PDF 선택",
            self._directory,
            "PDF 파일 (*.pdf)",
        )
        if not paths:
            return
        self._directory = str(Path(paths[0]).parent)
        errors: list[str] = []
        added = 0
        for path in paths:
            try:
                name, page_count = inspect_pdf(path)
            except PdfDocumentError as exc:
                errors.append(f"{Path(path).name}: {exc}")
                continue
            item = QListWidgetItem()
            item.setData(_PATH_ROLE, path)
            item.setData(_COUNT_ROLE, page_count)
            item.setData(_NAME_ROLE, name)
            item.setToolTip(path)
            self._list.addItem(item)
            added += 1
        if added and not errors:
            self._error.setText("")
        elif errors:
            self._error.setText("\n".join(errors))
        self._refresh_summary()
        if self._list.count() and self._list.currentRow() < 0:
            self._list.setCurrentRow(self._list.count() - 1)

    def _move_up(self) -> None:
        self._move(-1)

    def _move_down(self) -> None:
        self._move(1)

    def _move(self, offset: int) -> None:
        row = self._list.currentRow()
        target = row + offset
        if row < 0 or target < 0 or target >= self._list.count():
            return
        item = self._list.takeItem(row)
        self._list.insertItem(target, item)
        self._list.setCurrentRow(target)
        self._refresh_summary()

    def _delete_current(self) -> None:
        row = self._list.currentRow()
        if row < 0:
            return
        self._list.takeItem(row)
        if self._list.count():
            self._list.setCurrentRow(min(row, self._list.count() - 1))
        self._refresh_summary()

    def _refresh_summary(self) -> None:
        total_pages = 0
        for row in range(self._list.count()):
            item = self._list.item(row)
            name = item.data(_NAME_ROLE)
            page_count = int(item.data(_COUNT_ROLE))
            total_pages += page_count
            item.setText(f"{row + 1}.   {name}     ·     {page_count}페이지")
        count = self._list.count()
        if count == 0:
            self._summary.setText("선택된 파일 없음")
        else:
            self._summary.setText(f"{count}개 파일  ·  총 {total_pages}페이지")
        self._sync_buttons()

    def _sync_buttons(self) -> None:
        row = self._list.currentRow()
        count = self._list.count()
        self._up.setEnabled(row > 0)
        self._down.setEnabled(0 <= row < count - 1)
        self._delete.setEnabled(row >= 0)

    def _collect_items(self) -> list[MergeItem]:
        items: list[MergeItem] = []
        for row in range(self._list.count()):
            item = self._list.item(row)
            items.append(
                MergeItem(
                    path=str(item.data(_PATH_ROLE)),
                    name=str(item.data(_NAME_ROLE)),
                    page_count=int(item.data(_COUNT_ROLE)),
                )
            )
        return items

    def _submit(self) -> None:
        """목록을 다시 확인한 뒤 미리보기로 넘긴다."""
        try:
            plan: MergePlan = build_merge_plan(self._collect_items())
        except PdfDocumentError as exc:
            self._error.setText(str(exc))
            return
        self._error.setText("")
        self.merge_requested.emit(plan)
