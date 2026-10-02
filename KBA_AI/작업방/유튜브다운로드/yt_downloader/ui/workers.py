"""분석과 다운로드를 UI 스레드 밖에서 실행한다."""

from __future__ import annotations

import threading

from PyQt5.QtCore import QThread, pyqtSignal

from core.analyzer import AnalyzeError, analyze_url
from core.downloader import DownloadCancelled, UserDownloadError, download_media


class AnalyzeWorker(QThread):
    """yt-dlp 분석을 백그라운드에서 수행한다."""

    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, url: str, parent=None) -> None:
        super().__init__(parent)
        self._url = url

    def run(self) -> None:
        try:
            self.succeeded.emit(analyze_url(self._url))
        except AnalyzeError as exc:
            self.failed.emit(str(exc))
        except Exception:
            self.failed.emit("알 수 없는 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.")


class DownloadWorker(QThread):
    """선택한 포맷 다운로드와 진행률 전달을 담당한다."""

    progress = pyqtSignal(object)
    succeeded = pyqtSignal(str)
    failed = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(
        self,
        url: str,
        option: object,
        output_dir: str,
        filename_stem: str,
        overwrite: bool,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._url = url
        self._option = option
        self._output_dir = output_dir
        self._filename_stem = filename_stem
        self._overwrite = overwrite
        self._cancel = threading.Event()

    def request_cancel(self) -> None:
        """진행 중인 다운로드에 중단을 요청한다."""
        self._cancel.set()

    def run(self) -> None:
        try:
            path = download_media(
                self._url,
                self._option,
                self._output_dir,
                self._filename_stem,
                overwrite=self._overwrite,
                progress_callback=self.progress.emit,
                should_cancel=self._cancel.is_set,
            )
        except DownloadCancelled:
            self.cancelled.emit()
            return
        except UserDownloadError as exc:
            self.failed.emit(str(exc))
            return
        except Exception:
            self.failed.emit("다운로드 중 알 수 없는 오류가 발생했습니다.")
            return
        self.succeeded.emit(path)
