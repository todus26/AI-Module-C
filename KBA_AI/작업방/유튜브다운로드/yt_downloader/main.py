"""유튜브 다운로더 진입점."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> None:
    """앱을 실행한다."""
    try:
        import yt_dlp  # noqa: F401
    except ImportError:
        print("yt-dlp가 설치되어 있지 않습니다. pip install -r requirements.txt 를 실행해 주세요.")
        sys.exit(1)

    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QFont
    from PyQt5.QtWidgets import QApplication

    import PyQt5.QtSvg as _qt_svg  # SVG 아이콘 플러그인을 불러온다.

    del _qt_svg

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Malgun Gothic", 10))
    app.setOrganizationName("KBA")
    app.setApplicationName("YouTubeDownloader")
    app.setApplicationDisplayName("유튜브 다운로더")

    from ui.main_window import MainWindow
    from ui.styles import build_stylesheet

    app.setStyleSheet(build_stylesheet())
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
