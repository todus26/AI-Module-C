"""유튜브 다운로더 메인 창."""

from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import QSettings, QStandardPaths, Qt, QUrl
from PyQt5.QtGui import QCloseEvent, QDesktopServices, QPixmap
from PyQt5.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.analyzer import VideoInfo, is_ffmpeg_available
from core.downloader import (
    ProgressUpdate,
    UserDownloadError,
    make_filename_stem,
    numbered_stem,
    output_directory_error,
    output_file,
)
from core.format_utils import format_duration
from core.url_validator import is_valid_youtube_url
from ui.styles import PRIMARY, WHITE, build_stylesheet
from ui.widgets import FormatTable, IconButton, load_icon
from ui.workers import AnalyzeWorker, DownloadWorker


class MainWindow(QWidget):
    """링크 입력부터 저장까지 한 화면에서 처리한다."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("root")
        self.setWindowTitle("유튜브 다운로더")
        self.resize(760, 720)
        self.setMinimumSize(640, 600)
        self.setStyleSheet(build_stylesheet())

        self._settings = QSettings("KBA", "YouTubeDownloader")
        self._ffmpeg_ok = is_ffmpeg_available()
        self._video_info: VideoInfo | None = None
        self._analyzed_url = ""
        self._analyzing = False
        self._downloading = False
        self._closing = False
        self._ignore_url_change = False
        self._analyze_worker: AnalyzeWorker | None = None
        self._download_worker: DownloadWorker | None = None

        self._build_ui()
        self._load_output_dir()
        self._update_action_states()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)

        title = QLabel("유튜브 다운로더")
        title.setObjectName("appTitle")
        root.addWidget(title)

        self.ffmpeg_banner = QLabel(
            "FFmpeg가 설치되어 있지 않습니다. 영상·음성 병합과 MP3 변환은 사용할 수 없고, "
            "병합이 필요 없는 포맷만 받을 수 있습니다."
        )
        self.ffmpeg_banner.setObjectName("ffmpegBanner")
        self.ffmpeg_banner.setWordWrap(True)
        self.ffmpeg_banner.setVisible(not self._ffmpeg_ok)
        root.addWidget(self.ffmpeg_banner)

        url_row = QHBoxLayout()
        url_row.setSpacing(8)
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("유튜브 링크를 붙여넣으세요")
        self.refresh_btn = IconButton(
            load_icon("refresh-cw.svg", PRIMARY),
            "입력 초기화",
        )
        self.analyze_btn = QPushButton("분석")
        self.analyze_btn.setObjectName("analyzeButton")
        self.analyze_btn.setCursor(Qt.PointingHandCursor)
        self.analyze_btn.setMinimumWidth(112)
        url_row.addWidget(self.url_edit, 1)
        url_row.addWidget(self.refresh_btn)
        url_row.addWidget(self.analyze_btn)
        root.addLayout(url_row)

        self.url_error = QLabel("")
        self.url_error.setObjectName("errorLabel")
        self.url_error.setWordWrap(True)
        self.url_error.setVisible(False)
        root.addWidget(self.url_error)

        folder_row = QHBoxLayout()
        folder_row.setSpacing(8)
        self.path_edit = QLineEdit()
        self.path_edit.setReadOnly(True)
        self.path_edit.setPlaceholderText("다운로드 폴더")
        self.folder_btn = QPushButton("폴더 선택")
        self.folder_btn.setObjectName("folderButton")
        self.folder_btn.setIcon(load_icon("folder.svg", PRIMARY))
        self.folder_btn.setCursor(Qt.PointingHandCursor)
        self.folder_btn.setMinimumWidth(116)
        folder_row.addWidget(self.path_edit, 1)
        folder_row.addWidget(self.folder_btn)
        root.addLayout(folder_row)

        self.folder_error = QLabel("")
        self.folder_error.setObjectName("errorLabel")
        self.folder_error.setWordWrap(True)
        self.folder_error.setVisible(False)
        root.addWidget(self.folder_error)

        self.video_card = QFrame()
        self.video_card.setObjectName("videoCard")
        card_layout = QHBoxLayout(self.video_card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(14)
        self.thumbnail = QLabel("썸네일 없음")
        self.thumbnail.setObjectName("thumbnail")
        self.thumbnail.setFixedSize(168, 94)
        self.thumbnail.setAlignment(Qt.AlignCenter)
        text_col = QVBoxLayout()
        text_col.setSpacing(4)
        self.video_title = QLabel("")
        self.video_title.setObjectName("videoTitle")
        self.video_title.setWordWrap(True)
        self.video_meta = QLabel("")
        self.video_meta.setObjectName("videoMeta")
        self.video_meta.setWordWrap(True)
        text_col.addWidget(self.video_title)
        text_col.addWidget(self.video_meta)
        text_col.addStretch(1)
        card_layout.addWidget(self.thumbnail)
        card_layout.addLayout(text_col, 1)
        self.video_card.setVisible(False)
        root.addWidget(self.video_card)

        self.hint_label = QLabel("링크를 분석하면 받을 수 있는 포맷이 여기에 표시됩니다.")
        self.hint_label.setObjectName("hintLabel")
        root.addWidget(self.hint_label)

        self.format_table = FormatTable()
        root.addWidget(self.format_table, 1)

        progress_row = QHBoxLayout()
        progress_row.setSpacing(12)
        self.progress = QProgressBar()
        self.progress.setObjectName("progressBar")
        self.progress.setRange(0, 1000)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress_label = QLabel("")
        self.progress_label.setObjectName("progressLabel")
        self.progress_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        progress_row.addWidget(self.progress, 1)
        progress_row.addWidget(self.progress_label)
        root.addLayout(progress_row)

        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)
        self.status_label.setMinimumHeight(22)
        root.addWidget(self.status_label)

        button_row = QHBoxLayout()
        button_row.setSpacing(8)
        self.download_btn = QPushButton("다운로드")
        self.download_btn.setObjectName("downloadButton")
        self.download_btn.setIcon(load_icon("download.svg", WHITE))
        self.download_btn.setCursor(Qt.PointingHandCursor)
        self.download_btn.setMinimumWidth(120)
        self.cancel_btn = QPushButton("취소")
        self.cancel_btn.setObjectName("cancelButton")
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.setMinimumWidth(88)
        self.open_folder_btn = QPushButton("폴더 열기")
        self.open_folder_btn.setObjectName("openFolderButton")
        self.open_folder_btn.setIcon(load_icon("folder.svg", PRIMARY))
        self.open_folder_btn.setCursor(Qt.PointingHandCursor)
        self.open_folder_btn.setVisible(False)
        button_row.addWidget(self.download_btn)
        button_row.addWidget(self.cancel_btn)
        button_row.addStretch(1)
        button_row.addWidget(self.open_folder_btn)
        root.addLayout(button_row)

        self.url_edit.textChanged.connect(self._on_url_changed)
        self.url_edit.returnPressed.connect(self._on_analyze)
        self.refresh_btn.clicked.connect(self._on_refresh_clicked)
        self.analyze_btn.clicked.connect(self._on_analyze)
        self.folder_btn.clicked.connect(self._on_choose_folder)
        self.format_table.itemSelectionChanged.connect(self._update_action_states)
        self.download_btn.clicked.connect(self._on_download)
        self.cancel_btn.clicked.connect(self._on_cancel)
        self.open_folder_btn.clicked.connect(self._on_open_folder)

    def _load_output_dir(self) -> None:
        saved = self._settings.value("output_dir", "")
        if not isinstance(saved, str) or not saved.strip():
            saved = self._default_download_dir()
        self.path_edit.setText(saved)
        self._show_folder_error(output_directory_error(saved) or "")

    def _default_download_dir(self) -> str:
        location = QStandardPaths.writableLocation(QStandardPaths.DownloadLocation)
        if location:
            return location
        return str(Path.home() / "Downloads")

    def _on_url_changed(self) -> None:
        if self._ignore_url_change:
            return
        self._set_url_error("")
        typed = self.url_edit.text().strip()
        if (
            self._video_info is not None
            and typed != self._analyzed_url
            and not self._analyzing
            and not self._downloading
        ):
            self._video_info = None
            self._analyzed_url = ""
            self.format_table.clear_formats()
            self.video_card.setVisible(False)
            self.hint_label.setVisible(True)
            self.open_folder_btn.setVisible(False)
            self._reset_progress()
        self._update_action_states()

    def _on_refresh_clicked(self) -> None:
        if self._analyzing or self._downloading:
            return
        if self._video_info is not None and not self._confirm_reset():
            return
        self._reset_content()

    def _confirm_reset(self) -> bool:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Question)
        box.setWindowTitle("입력 초기화")
        box.setText("입력한 내용과 분석 결과를 모두 지울까요?")
        confirm = box.addButton("지우기", QMessageBox.YesRole)
        box.addButton("취소", QMessageBox.NoRole)
        box.setDefaultButton(box.buttons()[-1])
        box.exec_()
        return box.clickedButton() is confirm

    def _reset_content(self) -> None:
        self._ignore_url_change = True
        self.url_edit.clear()
        self._ignore_url_change = False
        self._video_info = None
        self._analyzed_url = ""
        self.format_table.clear_formats()
        self.video_card.setVisible(False)
        self.hint_label.setVisible(True)
        self.thumbnail.setPixmap(QPixmap())
        self.thumbnail.setText("썸네일 없음")
        self.video_title.clear()
        self.video_meta.clear()
        self.open_folder_btn.setVisible(False)
        self._set_url_error("")
        self._set_status("")
        self._reset_progress()
        self._update_action_states()

    def _on_choose_folder(self) -> None:
        if self._analyzing or self._downloading:
            return
        current = self.path_edit.text().strip() or self._default_download_dir()
        selected = QFileDialog.getExistingDirectory(self, "다운로드 폴더 선택", current)
        if not selected:
            return
        self.path_edit.setText(selected)
        self._settings.setValue("output_dir", selected)
        self._show_folder_error(output_directory_error(selected) or "")

    def _on_analyze(self) -> None:
        if self._analyzing or self._downloading:
            return
        url = self.url_edit.text().strip()
        if not url:
            self._set_url_error("유튜브 링크를 입력해 주세요.")
            return
        if not is_valid_youtube_url(url):
            self._set_url_error(
                "지원하지 않는 링크입니다. youtube.com/watch, youtu.be, shorts 링크를 입력해 주세요."
            )
            return

        self._set_url_error("")
        self._video_info = None
        self._analyzed_url = url
        self.format_table.clear_formats()
        self.video_card.setVisible(False)
        self.hint_label.setVisible(True)
        self.open_folder_btn.setVisible(False)
        self._reset_progress()
        self._analyzing = True
        self._set_status("분석 중...")
        self._update_action_states()

        worker = AnalyzeWorker(url, self)
        self._analyze_worker = worker
        worker.succeeded.connect(self._on_analyze_success)
        worker.failed.connect(self._on_analyze_failed)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _on_analyze_success(self, info: object) -> None:
        if self._closing or not isinstance(info, VideoInfo):
            return
        self._analyzing = False
        self._video_info = info
        self._show_video(info)
        self.format_table.set_formats(list(info.formats))
        self.hint_label.setVisible(not info.formats)
        self._set_status("분석이 완료되었습니다. 포맷을 선택하세요.", "success")
        self._update_action_states()

    def _on_analyze_failed(self, message: str) -> None:
        if self._closing:
            return
        self._analyzing = False
        self._video_info = None
        self._set_url_error(message)
        self._set_status("")
        self._update_action_states()

    def _show_video(self, info: VideoInfo) -> None:
        self.video_title.setText(info.title)
        length = format_duration(info.duration_seconds)
        if length == "알 수 없음":
            length_text = "재생 시간 알 수 없음"
        else:
            length_text = f"재생 시간 {length}"
        self.video_meta.setText(f"{info.channel}    {length_text}")
        self._set_thumbnail(info.thumbnail_bytes)
        self.video_card.setVisible(True)

    def _set_thumbnail(self, data: bytes | None) -> None:
        if not data:
            self.thumbnail.setPixmap(QPixmap())
            self.thumbnail.setText("썸네일 없음")
            return
        pixmap = QPixmap()
        if not pixmap.loadFromData(data):
            self.thumbnail.setPixmap(QPixmap())
            self.thumbnail.setText("썸네일 없음")
            return
        dpr = self.thumbnail.devicePixelRatioF()
        scaled = pixmap.scaled(
            max(1, int(168 * dpr)),
            max(1, int(94 * dpr)),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        scaled.setDevicePixelRatio(dpr)
        self.thumbnail.setText("")
        self.thumbnail.setPixmap(scaled)

    def _on_download(self) -> None:
        if self._analyzing or self._downloading or self._video_info is None:
            return
        option = self.format_table.selected_format()
        if option is None:
            self._set_status("다운로드할 포맷을 선택해 주세요.", "error")
            return
        folder = self.path_edit.text().strip()
        folder_error = output_directory_error(folder)
        if folder_error:
            self._show_folder_error(folder_error)
            return
        self._show_folder_error("")

        stem = make_filename_stem(self._video_info.title, folder, option.output_ext)
        target = output_file(folder, stem, option.output_ext)
        overwrite = False
        if target.exists():
            choice = self._ask_conflict(target.name)
            if choice == "cancel":
                return
            if choice == "rename":
                try:
                    stem = numbered_stem(folder, stem, option.output_ext)
                except UserDownloadError as exc:
                    self._set_status(str(exc), "error")
                    return
            else:
                overwrite = True

        self.open_folder_btn.setVisible(False)
        self._reset_progress()
        self._downloading = True
        self._set_status("")
        self.progress_label.setText("다운로드 준비 중...")
        self._update_action_states()

        worker = DownloadWorker(
            self._analyzed_url,
            option,
            folder,
            stem,
            overwrite,
            self,
        )
        self._download_worker = worker
        worker.progress.connect(self._on_progress)
        worker.succeeded.connect(self._on_download_success)
        worker.failed.connect(self._on_download_failed)
        worker.cancelled.connect(self._on_download_cancelled)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _ask_conflict(self, filename: str) -> str:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Question)
        box.setWindowTitle("파일 이름 충돌")
        box.setText(f"같은 이름의 파일이 이미 있습니다.\n{filename}")
        box.setInformativeText("어떻게 저장할까요?")
        overwrite = box.addButton("덮어쓰기", QMessageBox.AcceptRole)
        rename = box.addButton("번호 붙여 저장", QMessageBox.ActionRole)
        cancel = box.addButton("취소", QMessageBox.RejectRole)
        box.setDefaultButton(cancel)
        box.exec_()
        clicked = box.clickedButton()
        if clicked is overwrite:
            return "overwrite"
        if clicked is rename:
            return "rename"
        return "cancel"

    def _on_progress(self, update: object) -> None:
        if self._closing or not isinstance(update, ProgressUpdate):
            return
        if update.phase == "processing":
            self.progress.setRange(0, 0)
            self.progress_label.setText("처리 중...")
            return
        if update.percent is None:
            self.progress.setRange(0, 0)
        else:
            if self.progress.maximum() == 0:
                self.progress.setRange(0, 1000)
            self.progress.setValue(int(update.percent * 10))
        self.progress_label.setText(_progress_text(update))

    def _on_download_success(self, _path: str) -> None:
        if self._closing:
            return
        self._downloading = False
        self.progress.setRange(0, 1000)
        self.progress.setValue(1000)
        self.progress_label.setText("100%")
        self._set_status("다운로드가 완료되었습니다.", "success")
        self.open_folder_btn.setVisible(True)
        self._update_action_states()

    def _on_download_failed(self, message: str) -> None:
        if self._closing:
            return
        self._downloading = False
        self._reset_progress()
        self._set_status(message, "error")
        self._update_action_states()

    def _on_download_cancelled(self) -> None:
        if self._closing:
            return
        self._downloading = False
        self._reset_progress()
        self._set_status("다운로드를 취소했습니다.")
        self._update_action_states()

    def _on_cancel(self) -> None:
        if self._download_worker is not None and self._download_worker.isRunning():
            self._download_worker.request_cancel()
            self.cancel_btn.setEnabled(False)
            self.progress_label.setText("취소하는 중...")

    def _on_open_folder(self) -> None:
        folder = self.path_edit.text().strip()
        if folder:
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def _set_url_error(self, message: str) -> None:
        self.url_error.setText(message)
        self.url_error.setVisible(bool(message))
        self.url_edit.setProperty("invalid", "true" if message else "false")
        self._repolish(self.url_edit)

    def _show_folder_error(self, message: str) -> None:
        self.folder_error.setText(message)
        self.folder_error.setVisible(bool(message))

    def _set_status(self, message: str, level: str = "normal") -> None:
        self.status_label.setText(message)
        self.status_label.setProperty("level", level)
        self._repolish(self.status_label)

    def _reset_progress(self) -> None:
        self.progress.setRange(0, 1000)
        self.progress.setValue(0)
        self.progress_label.clear()

    def _update_action_states(self) -> None:
        busy = self._analyzing or self._downloading
        self.analyze_btn.setEnabled(not busy)
        self.analyze_btn.setText("분석 중..." if self._analyzing else "분석")
        self.folder_btn.setEnabled(not busy)
        self.url_edit.setReadOnly(busy)
        selected = self.format_table.selected_format() if not busy else None
        self.download_btn.setEnabled(selected is not None)
        self.cancel_btn.setEnabled(self._downloading)
        has_content = bool(self.url_edit.text().strip()) or self._video_info is not None
        self.refresh_btn.setEnabled((not busy) and has_content)

    def _repolish(self, widget: QWidget) -> None:
        style = widget.style()
        style.unpolish(widget)
        style.polish(widget)

    def closeEvent(self, event: QCloseEvent) -> None:
        self._closing = True
        self._stop_workers()
        event.accept()

    def _stop_workers(self) -> None:
        if _thread_is_running(self._download_worker):
            self._download_worker.request_cancel()
            if not self._download_worker.wait(5000) and _thread_is_running(self._download_worker):
                self._download_worker.terminate()
                self._download_worker.wait(1000)
        if _thread_is_running(self._analyze_worker):
            if not self._analyze_worker.wait(2000) and _thread_is_running(self._analyze_worker):
                self._analyze_worker.terminate()
                self._analyze_worker.wait(1000)


def _thread_is_running(worker: object) -> bool:
    """워커가 아직 살아 있고 실행 중인지 확인한다."""
    if worker is None:
        return False
    try:
        return bool(worker.isRunning())  # type: ignore[attr-defined]
    except RuntimeError:
        return False


def _progress_text(update: ProgressUpdate) -> str:
    parts: list[str] = []
    if update.percent is not None:
        parts.append(f"{update.percent:.1f}%")
    if update.speed_text:
        parts.append(update.speed_text)
    if update.eta_text:
        parts.append(f"남은 시간 {update.eta_text}")
    return " · ".join(parts) if parts else "다운로드 중..."
