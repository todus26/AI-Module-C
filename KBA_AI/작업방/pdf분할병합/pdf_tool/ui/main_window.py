"""사이드바와 분할, 병합, 미리보기, 저장 화면을 연결한다."""

from datetime import datetime

from PyQt5.QtCore import QSize, Qt
from PyQt5.QtGui import QCloseEvent, QIcon
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.exporter import part_from_merge, parts_from_split
from core.page_parser import SplitMode
from core.pdf_merger import MergePlan
from core.pdf_splitter import SplitPlan
from ui.merge_page import MergePage
from ui.preview_page import PreviewPage
from ui.save_page import SavePage, WorkItem
from ui.split_page import SplitPage
from ui.styles import icon_path


class MainWindow(QMainWindow):
    """좌측 탐색과 우측 화면 스택을 관리한다."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PDF 분할/병합")
        self.resize(1100, 740)
        self.setMinimumSize(980, 640)

        window_icon = icon_path("split.svg")
        if window_icon.exists():
            self.setWindowIcon(QIcon(str(window_icon)))

        self._nav_buttons: list[QPushButton] = []
        self._navigation_enabled = True
        self._next_id = 1
        self._pending: tuple[str, SplitPlan | MergePlan] | None = None

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_sidebar())

        self.stack = QStackedWidget()
        self.stack.setObjectName("contentStack")
        root.addWidget(self.stack, 1)

        self._split = SplitPage()
        self._merge = MergePage()
        self._save = SavePage()
        self._preview = PreviewPage()

        self._add_nav_page("분할", "split.svg", self._split)
        self._add_nav_page("병합", "merge.svg", self._merge)
        self._add_nav_page("저장 내역", "save.svg", self._save)
        self.stack.addWidget(self._preview)

        self._split.split_requested.connect(self._open_split_preview)
        self._merge.merge_requested.connect(self._open_merge_preview)
        self._preview.edit_requested.connect(self._return_to_editor)
        self._preview.confirm_requested.connect(self._confirm_pending)
        self._save.busy_changed.connect(lambda busy: self._set_navigation_enabled(not busy))
        self.select_page(0)

    def select_page(self, index: int) -> None:
        """사이드바에 등록된 화면으로 이동하고 선택 상태를 맞춘다."""
        if not self._navigation_enabled:
            return
        if index < 0 or index >= len(self._nav_buttons):
            return
        self.stack.setCurrentIndex(index)
        for button_index, button in enumerate(self._nav_buttons):
            button.setProperty("active", button_index == index)
            button.style().unpolish(button)
            button.style().polish(button)
            button.update()

    def closeEvent(self, event: QCloseEvent) -> None:
        """썸네일과 저장 작업이 남은 채로 프로세스가 끝나지 않게 한다."""
        self._preview.shutdown()
        self._save.shutdown()
        event.accept()

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setAttribute(Qt.WA_StyledBackground, True)
        sidebar.setFixedWidth(232)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(20, 28, 20, 24)
        layout.setSpacing(6)

        brand = QLabel("PDF 도구")
        brand.setObjectName("brandTitle")
        subtitle = QLabel("분할 · 병합")
        subtitle.setObjectName("brandSub")
        layout.addWidget(brand)
        layout.addWidget(subtitle)
        layout.addSpacing(22)

        self._nav_layout = QVBoxLayout()
        self._nav_layout.setSpacing(4)
        layout.addLayout(self._nav_layout)
        layout.addStretch(1)
        return sidebar

    def _add_nav_page(self, title: str, icon_name: str, page: QWidget) -> None:
        index = self.stack.addWidget(page)
        button = QPushButton(title)
        button.setObjectName("navButton")
        button.setCursor(Qt.PointingHandCursor)
        button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        button.setProperty("active", False)
        icon = icon_path(icon_name)
        if icon.exists():
            button.setIcon(QIcon(str(icon)))
            button.setIconSize(QSize(18, 18))
        button.clicked.connect(lambda _checked=False, page_index=index: self.select_page(page_index))
        self._nav_buttons.append(button)
        self._nav_layout.addWidget(button)

    def _open_split_preview(self, plan: SplitPlan) -> None:
        self._pending = ("split", plan)
        self._preview.show_split(plan)
        self.stack.setCurrentWidget(self._preview)

    def _open_merge_preview(self, plan: MergePlan) -> None:
        self._pending = ("merge", plan)
        self._preview.show_merge(plan)
        self.stack.setCurrentWidget(self._preview)

    def _return_to_editor(self, origin: str) -> None:
        """입력값은 각 화면 위젯이 그대로 들고 있으므로 페이지만 되돌린다."""
        self.select_page(0 if origin == "split" else 1)

    def _confirm_pending(self) -> None:
        if self._pending is None:
            return
        kind, plan = self._pending
        now = datetime.now()
        item_id = self._next_id
        self._next_id += 1
        if kind == "split" and isinstance(plan, SplitPlan):
            parts = parts_from_split(plan.source_name, plan.source_path, plan.groups, plan.labels)
            labels = " / ".join(plan.labels)
            if len(labels) > 90:
                labels = labels[:87] + "..."
            title = f"분할 · {plan.source_name}"
            summary = f"{SplitMode(plan.mode).label} · 파일 {len(parts)}개 · {labels}"
        elif isinstance(plan, MergePlan):
            stamp = now.strftime("%H%M%S") + f"_{item_id}"
            parts = (
                part_from_merge(
                    [(item.path, item.page_count) for item in plan.items],
                    len(plan.items),
                    stamp,
                ),
            )
            names = " · ".join(item.name for item in plan.items)
            if len(names) > 90:
                names = names[:87] + "..."
            title = f"병합 · {len(plan.items)}개 파일"
            summary = f"총 {plan.total_pages}페이지 · {names}"
        else:
            return

        self._save.add_work(
            WorkItem(
                item_id=item_id,
                title=title,
                summary=summary,
                created_text=now.strftime("%Y-%m-%d %H:%M"),
                parts=tuple(parts),
            )
        )
        self.select_page(2)

    def _set_navigation_enabled(self, enabled: bool) -> None:
        """저장 중에는 다른 화면으로 이동하지 못하게 막는다."""
        self._navigation_enabled = enabled
        for button in self._nav_buttons:
            button.setEnabled(enabled)
