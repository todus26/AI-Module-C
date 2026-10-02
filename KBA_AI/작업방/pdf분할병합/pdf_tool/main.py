"""PDF 분할/병합 데스크톱 앱 진입점.

실행:
    python main.py
"""

import sys

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QApplication

import PyQt5.QtSvg  # SVG 아이콘 엔진을 실행 파일에 포함하기 위한 import

from ui.main_window import MainWindow
from ui.styles import APP_STYLESHEET


def main() -> None:
    """스타일을 적용한 메인 윈도우를 띄운다."""
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("PDF 분할/병합")
    app.setStyle("Fusion")

    font = QFont("Malgun Gothic")
    font.setPointSize(10)
    app.setFont(font)
    app.setStyleSheet(APP_STYLESHEET)

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
