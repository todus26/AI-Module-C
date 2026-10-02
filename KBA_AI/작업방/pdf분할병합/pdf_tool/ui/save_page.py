"""세션 안의 작업 내역을 PDF 또는 Word로 저장하는 화면."""

from dataclasses import dataclass
from pathlib import Path

from PyQt5.QtCore import QSize, Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from core.exporter import ConflictPolicy, ExportPart, dedupe_stems, export_files, resolve_conflict
from core.pdf_splitter import PdfDocumentError
from ui.widgets import create_button, create_card, error_label, section_label


@dataclass
class WorkItem:
    """앱을 켜 둔 동안만 보관하는 분할/병합 결과."""

    item_id: int
    title: str
    summary: str
    created_text: str
    parts: tuple[ExportPart, ...]


class ExportWorker(QThread):
    """파일 저장과 Word 변환을 UI 스레드 밖에서 실행한다."""

    progress = pyqtSignal(int, int, str)
    succeeded = pyqtSignal(list)
    failed = pyqtSignal(str)

    def __init__(
        self,
        jobs: list[tuple[tuple, Path]],
        kind: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._jobs = jobs
        self._kind = kind

    def run(self) -> None:
        try:
            written = export_files(
                self._jobs,
                self._kind,
                progress=lambda current, total, message: self.progress.emit(current, total, message),
            )
        except PdfDocumentError as exc:
            self.failed.emit(str(exc))
            return
        except Exception as exc:
            self.failed.emit(f"저장 중 오류가 발생했습니다. {exc}")
            return
        self.succeeded.emit([str(path) for path in written])


class SavePage(QWidget):
    """작업 내역을 고르고 저장 위치와 형식을 정한다."""

    busy_changed = pyqtSignal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("contentPage")
        self._works: dict[int, WorkItem] = {}
        self._directory = str(Path.home())
        self._worker: ExportWorker | None = None
        self._busy = False

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 32, 36, 28)
        root.setSpacing(8)

        title = QLabel("저장 내역")
        title.setObjectName("pageTitle")
        description = QLabel("이번 실행에서 확인한 결과를 저장합니다. 여러 항목을 고를 수 있으며, 앱을 닫으면 목록은 사라집니다.")
        description.setObjectName("pageHint")
        description.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(description)
        root.addSpacing(12)

        format_card, format_layout = create_card()
        format_layout.addWidget(section_label("출력 형식"))
        format_row = QHBoxLayout()
        format_row.setSpacing(24)
        self._pdf = QRadioButton("PDF")
        self._word = QRadioButton("Word (.docx)")
        self._pdf.setChecked(True)
        self._format_group = QButtonGroup(self)
        self._format_group.addButton(self._pdf)
        self._format_group.addButton(self._word)
        format_row.addWidget(self._pdf)
        format_row.addWidget(self._word)
        format_row.addStretch(1)
        format_layout.addLayout(format_row)
        self._format_hint = QLabel("Word로 저장하면 변환이 끝난 뒤에야 다른 작업을 할 수 있습니다.")
        self._format_hint.setObjectName("pageHint")
        self._format_hint.setWordWrap(True)
        format_layout.addWidget(self._format_hint)
        root.addWidget(format_card)

        history_card, history_layout = create_card()
        history_layout.addWidget(section_label("작업 내역"))
        self._empty = QLabel("아직 저장할 결과가 없습니다. 분할 또는 병합을 실행한 뒤 확인해 주세요.")
        self._empty.setObjectName("pageHint")
        self._empty.setWordWrap(True)
        history_layout.addWidget(self._empty)

        self._list = QListWidget()
        self._list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._list.setWordWrap(True)
        self._list.setUniformItemSizes(False)
        self._list.setMinimumHeight(180)
        history_layout.addWidget(self._list, 1)

        self._notice = QLabel("Word로 변환 중입니다. 이 작업은 취소할 수 없습니다.")
        self._notice.setObjectName("busyNotice")
        self._notice.setWordWrap(True)
        self._notice.setVisible(False)
        history_layout.addWidget(self._notice)

        self._progress = QProgressBar()
        self._progress.setVisible(False)
        self._progress.setTextVisible(False)
        history_layout.addWidget(self._progress)

        self._status = QLabel("")
        self._status.setObjectName("pageHint")
        self._status.setWordWrap(True)
        history_layout.addWidget(self._status)

        self._error = error_label()
        history_layout.addWidget(self._error)
        root.addWidget(history_card, 1)

        action_row = QHBoxLayout()
        action_row.addStretch(1)
        self._save_button = create_button("저장", "primaryButton", "save_white.svg")
        self._save_button.setMinimumWidth(120)
        self._save_button.clicked.connect(self._save)
        action_row.addWidget(self._save_button)
        root.addSpacing(8)
        root.addLayout(action_row)

    def add_work(self, item: WorkItem) -> None:
        """방금 확인한 결과를 목록 맨 위에 두고 선택한다."""
        self._works[item.item_id] = item
        row = QListWidgetItem(f"{item.title}     {item.created_text}\n{item.summary}")
        row.setData(Qt.UserRole, item.item_id)
        row.setSizeHint(QSize(0, 58))
        row.setToolTip(f"{item.title}\n{item.summary}\n{item.created_text}")
        self._list.insertItem(0, row)
        self._list.clearSelection()
        row.setSelected(True)
        self._list.setCurrentItem(row)
        self._list.scrollToItem(row)
        self._empty.setVisible(False)
        self._error.setText("")
        self._status.setText("선택한 결과를 저장할 수 있습니다.")

    def shutdown(self) -> None:
        """저장이 끝나기 전에는 창을 바로 닫지 않는다."""
        worker = self._worker
        if worker is not None and worker.isRunning():
            worker.wait()

    def _selected_works(self) -> list[WorkItem]:
        rows = sorted({index.row() for index in self._list.selectedIndexes()})
        works: list[WorkItem] = []
        for row in rows:
            item_id = self._list.item(row).data(Qt.UserRole)
            work = self._works.get(int(item_id))
            if work is not None:
                works.append(work)
        return works

    def _save(self) -> None:
        if self._busy:
            return
        works = self._selected_works()
        if not works:
            self._error.setText("저장할 항목을 선택해 주세요.")
            return

        word = self._word.isChecked()
        kind = "docx" if word else "pdf"
        extension = ".docx" if word else ".pdf"
        parts: list[ExportPart] = []
        for work in works:
            parts.extend(work.parts)
        stems = dedupe_stems([part.suggested_stem for part in parts])
        names = [f"{stem}{extension}" for stem in stems]

        try:
            targets = self._ask_targets(names)
        except PdfDocumentError as exc:
            self._error.setText(str(exc))
            return
        if not targets:
            return

        jobs = [(part.pages, target) for part, target in zip(parts, targets)]
        self._error.setText("")
        self._status.setText("저장을 준비하고 있습니다.")
        self._progress.setMaximum(len(jobs))
        self._progress.setValue(0)
        self._set_busy(True, word)

        worker = ExportWorker(jobs, kind, self)
        worker.progress.connect(self._on_progress)
        worker.succeeded.connect(self._on_success)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(worker.deleteLater)
        self._worker = worker
        worker.start()

    def _ask_targets(self, names: list[str]) -> list[Path] | None:
        """파일 하나면 저장 대화상자, 여러 파일이면 폴더를 고른다."""
        if len(names) == 1:
            selected, _filter = QFileDialog.getSaveFileName(
                self,
                "저장 위치",
                str(Path(self._directory) / names[0]),
                "Word 문서 (*.docx)" if names[0].lower().endswith(".docx") else "PDF 파일 (*.pdf)",
                options=QFileDialog.DontConfirmOverwrite,
            )
            if not selected:
                return None
            path = Path(selected)
            suffix = Path(names[0]).suffix
            if path.suffix.lower() != suffix:
                path = path.with_suffix(suffix)
            self._directory = str(path.parent)
            return self._resolve_many([path])

        folder = QFileDialog.getExistingDirectory(self, "저장할 폴더", self._directory)
        if not folder:
            return None
        self._directory = folder
        return self._resolve_many([Path(folder) / name for name in names])

    def _resolve_many(self, paths: list[Path]) -> list[Path] | None:
        policy = self._policy_for(paths)
        if policy is None:
            return None
        return [resolve_conflict(path, policy) for path in paths]

    def _policy_for(self, paths: list[Path]) -> ConflictPolicy | None:
        existing = [path.name for path in paths if path.exists()]
        if not existing:
            return ConflictPolicy.OVERWRITE
        box = QMessageBox(self)
        box.setWindowTitle("파일 이름 충돌")
        box.setIcon(QMessageBox.Warning)
        box.setText("같은 이름의 파일이 이미 있습니다. 어떻게 저장할지 선택해 주세요.")
        preview = "\n".join(existing[:6])
        if len(existing) > 6:
            preview += f"\n외 {len(existing) - 6}개"
        box.setInformativeText(preview)
        overwrite = box.addButton("덮어쓰기", QMessageBox.AcceptRole)
        numbered = box.addButton("번호 붙이기", QMessageBox.ActionRole)
        box.addButton("취소", QMessageBox.RejectRole)
        box.exec_()
        clicked = box.clickedButton()
        if clicked is overwrite:
            return ConflictPolicy.OVERWRITE
        if clicked is numbered:
            return ConflictPolicy.AUTONUMBER
        return None

    def _on_progress(self, current: int, total: int, message: str) -> None:
        self._progress.setMaximum(max(total, 1))
        self._progress.setValue(current)
        self._status.setText(message)

    def _on_success(self, paths: list) -> None:
        self._set_busy(False, False)
        self._progress.setVisible(False)
        self._status.setText(f"{len(paths)}개 파일을 저장했습니다.")
        shown = "\n".join(str(path) for path in paths[:8])
        if len(paths) > 8:
            shown += f"\n외 {len(paths) - 8}개"
        QMessageBox.information(self, "저장 완료", f"{len(paths)}개 파일을 저장했습니다.\n\n{shown}")

    def _on_failed(self, message: str) -> None:
        self._set_busy(False, False)
        self._progress.setVisible(False)
        self._status.setText("")
        self._error.setText(message)

    def _set_busy(self, busy: bool, word: bool) -> None:
        self._busy = busy
        self._save_button.setEnabled(not busy)
        self._list.setEnabled(not busy)
        self._pdf.setEnabled(not busy)
        self._word.setEnabled(not busy)
        self._notice.setVisible(busy and word)
        self._progress.setVisible(busy)
        self.busy_changed.emit(busy)
