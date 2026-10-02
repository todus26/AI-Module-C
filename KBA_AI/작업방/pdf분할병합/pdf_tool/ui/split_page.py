"""PDF를 올리고 다섯 가지 방식으로 분할 입력을 받는 화면."""

from pathlib import Path

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.page_parser import PageParseError, SplitMode, groups_for_mode
from core.pdf_splitter import PdfDocumentError, SplitPlan, build_split_plan, inspect_pdf
from ui.widgets import create_button, create_card, error_label, section_label


_MODE_HINTS = {
    SplitMode.PAGES: "선택한 페이지만 하나의 PDF로 추출합니다.",
    SplitMode.RANGES: "입력한 범위마다 별도의 PDF를 만듭니다.",
    SplitMode.CHUNK: "입력한 페이지 수만큼 잘라 여러 PDF를 만듭니다.",
    SplitMode.SPLIT_AT: "입력한 페이지 뒤에서 나눕니다. 예: 4, 9 이면 1-4 / 5-9 / 10-끝 입니다.",
    SplitMode.EQUAL: "전체를 N개 파일로 나누고, 나머지는 앞 파일부터 1페이지씩 넣습니다.",
}

_PLACEHOLDERS = {
    SplitMode.PAGES: "예: 1, 3, 5",
    SplitMode.RANGES: "예: 1-3, 5-8",
    SplitMode.CHUNK: "예: 3",
    SplitMode.SPLIT_AT: "예: 4, 9",
    SplitMode.EQUAL: "예: 3",
}


class SplitPage(QWidget):
    """분할 입력 화면. 위젯 상태는 화면을 떠나도 유지된다."""

    split_requested = pyqtSignal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("contentPage")
        self._path: str | None = None
        self._page_count = 0
        self._directory = str(Path.home())
        self._mode = SplitMode.PAGES

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 32, 36, 28)
        root.setSpacing(8)

        title = QLabel("분할")
        title.setObjectName("pageTitle")
        description = QLabel("PDF를 선택한 뒤 나누는 방식을 입력합니다. 분할을 눌러도 바로 저장되지 않습니다.")
        description.setObjectName("pageHint")
        description.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(description)
        root.addSpacing(12)

        scroll, content_layout = _scroll_body()
        content_layout.addWidget(self._build_file_card())
        content_layout.addWidget(self._build_mode_card())
        content_layout.addStretch(1)
        root.addWidget(scroll, 1)

        action_row = QHBoxLayout()
        action_row.addStretch(1)
        self._split_button = create_button("분할", "primaryButton", "split_white.svg")
        self._split_button.setMinimumWidth(120)
        self._split_button.clicked.connect(self._submit)
        action_row.addWidget(self._split_button)
        root.addSpacing(8)
        root.addLayout(action_row)

    def _build_file_card(self) -> QFrame:
        card, layout = create_card()
        layout.addWidget(section_label("PDF 파일"))

        row = QHBoxLayout()
        row.setSpacing(16)
        upload = create_button("PDF 선택", "secondaryButton", "upload.svg")
        upload.clicked.connect(self._choose_file)
        self._file_name = QLabel("선택된 파일 없음")
        self._file_name.setObjectName("sectionTitle")
        self._file_name.setWordWrap(True)
        self._file_meta = QLabel("파일을 선택하면 페이지 수가 표시됩니다.")
        self._file_meta.setObjectName("pageHint")
        text_box = QVBoxLayout()
        text_box.setSpacing(4)
        text_box.addWidget(self._file_name)
        text_box.addWidget(self._file_meta)
        row.addWidget(upload)
        row.addLayout(text_box, 1)
        layout.addLayout(row)

        self._file_error = error_label()
        layout.addWidget(self._file_error)
        return card

    def _build_mode_card(self) -> QFrame:
        card, layout = create_card()
        layout.addWidget(section_label("분할 방식"))

        for mode in SplitMode:
            button = QRadioButton(mode.label)
            layout.addWidget(button)
            if mode is SplitMode.PAGES:
                button.setChecked(True)
            button.toggled.connect(lambda checked, selected=mode: self._on_mode_toggled(checked, selected))

        self._mode_hint = QLabel(_MODE_HINTS[SplitMode.PAGES])
        self._mode_hint.setObjectName("pageHint")
        self._mode_hint.setWordWrap(True)
        layout.addWidget(self._mode_hint)

        self._expression = QLineEdit()
        self._expression.setPlaceholderText(_PLACEHOLDERS[SplitMode.PAGES])
        self._expression.textChanged.connect(lambda _text: self._validate(show_empty=False))
        self._expression.returnPressed.connect(self._submit)
        layout.addWidget(self._expression)

        self._input_error = error_label()
        layout.addWidget(self._input_error)
        return card

    def _choose_file(self) -> None:
        """파일 대화상자로 PDF를 고르고 페이지 수를 표시한다."""
        path, _selected = QFileDialog.getOpenFileName(
            self,
            "PDF 선택",
            self._directory,
            "PDF 파일 (*.pdf)",
        )
        if not path:
            return
        self._directory = str(Path(path).parent)
        try:
            name, page_count = inspect_pdf(path)
        except PdfDocumentError as exc:
            self._file_error.setText(str(exc))
            return

        self._path = path
        self._page_count = page_count
        self._file_name.setText(name)
        self._file_name.setToolTip(path)
        self._file_meta.setText(f"총 {page_count}페이지")
        self._file_error.setText("")
        self._validate(show_empty=False)

    def _on_mode_toggled(self, checked: bool, mode: SplitMode) -> None:
        if not checked:
            return
        self._mode = mode
        self._mode_hint.setText(_MODE_HINTS[mode])
        self._expression.setPlaceholderText(_PLACEHOLDERS[mode])
        self._validate(show_empty=False)

    def _validate(self, show_empty: bool) -> bool:
        """입력창 아래에 오류를 표시하고, 통과하면 True를 반환한다."""
        text = self._expression.text().strip()
        if not self._path:
            if show_empty:
                self._file_error.setText("PDF 파일을 먼저 선택해 주세요.")
            return False
        if not text:
            self._input_error.setText("값을 입력해 주세요." if show_empty else "")
            return False
        try:
            groups_for_mode(self._mode, text, self._page_count)
        except PageParseError as exc:
            self._input_error.setText(str(exc))
            return False
        self._input_error.setText("")
        return True

    def _submit(self) -> None:
        """검증을 통과하면 저장 없이 미리보기 요청만 보낸다."""
        if not self._validate(show_empty=True) or not self._path:
            return
        try:
            plan: SplitPlan = build_split_plan(self._path, self._mode, self._expression.text())
        except PageParseError as exc:
            self._input_error.setText(str(exc))
            return
        except PdfDocumentError as exc:
            self._file_error.setText(str(exc))
            return
        self._file_error.setText("")
        self._input_error.setText("")
        self.split_requested.emit(plan)


def _scroll_body() -> tuple[QScrollArea, QVBoxLayout]:
    scroll = QScrollArea()
    scroll.setObjectName("pageScroll")
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.NoFrame)
    inner = QWidget()
    inner.setObjectName("contentPage")
    inner.setAttribute(Qt.WA_StyledBackground, True)
    layout = QVBoxLayout(inner)
    layout.setContentsMargins(0, 0, 8, 0)
    layout.setSpacing(16)
    scroll.setWidget(inner)
    return scroll, layout
