"""앱 전역 색상과 QSS.

그라데이션과 그림자는 사용하지 않는다.
"""

import sys
from pathlib import Path

# Shifty Blue 팔레트
PRIMARY = "#2F5D8C"
PRIMARY_HOVER = "#264E77"
PRIMARY_LIGHT = "#E8EFF7"
BACKGROUND = "#F7F9FC"
BORDER = "#D5DEE9"
TEXT = "#1F2A37"
ERROR = "#C0392B"

# 팔레트를 보조하는 무채색. 본문보다 약한 설명 문구와 카드 표면에 쓴다.
SURFACE = "#FFFFFF"
TEXT_SECONDARY = "#5C6B7A"
DISABLED = "#9AA8B8"


def icon_path(name: str) -> Path:
    """resources/icons 아래 SVG 경로를 반환한다.

    PyInstaller로 만든 실행 파일에서는 압축을 푼 임시 폴더를 기준으로 찾는다.

    Args:
        name: 파일 이름. 예: ``split.svg``

    Returns:
        아이콘 파일의 절대 경로. 파일 존재 여부는 호출하는 쪽에서 확인한다.
    """
    if getattr(sys, "frozen", False):
        root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    else:
        root = Path(__file__).resolve().parent.parent
    return root / "resources" / "icons" / name


APP_STYLESHEET = f"""
QWidget {{
    color: {TEXT};
    font-family: "Malgun Gothic", "맑은 고딕", "Segoe UI", sans-serif;
    font-size: 13px;
}}

QMainWindow {{
    background: {BACKGROUND};
}}

QWidget#contentPage {{
    background: {BACKGROUND};
}}

QWidget#sidebar {{
    background: {SURFACE};
    border-right: 1px solid {BORDER};
}}

QLabel#brandTitle {{
    font-size: 18px;
    font-weight: 600;
    color: {TEXT};
}}

QLabel#brandSub {{
    font-size: 12px;
    color: {TEXT_SECONDARY};
}}

QPushButton#navButton {{
    text-align: left;
    padding: 10px 14px;
    border: none;
    border-radius: 8px;
    background: transparent;
    color: {TEXT};
    font-size: 14px;
}}

QPushButton#navButton:hover {{
    background: {PRIMARY_LIGHT};
}}

QPushButton#navButton[active="true"] {{
    background: {PRIMARY_LIGHT};
    color: {PRIMARY};
    font-weight: 600;
}}

QLabel#pageTitle {{
    font-size: 22px;
    font-weight: 600;
    color: {TEXT};
}}

QLabel#pageHint {{
    font-size: 13px;
    color: {TEXT_SECONDARY};
}}

QLabel#errorLabel {{
    color: {ERROR};
    font-size: 12px;
}}

QFrame#card {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}

QPushButton#primaryButton {{
    background: {PRIMARY};
    color: {SURFACE};
    border: none;
    border-radius: 8px;
    padding: 8px 18px;
    font-weight: 600;
    min-height: 20px;
}}

QPushButton#primaryButton:hover {{
    background: {PRIMARY_HOVER};
}}

QPushButton#primaryButton:disabled {{
    background: {BORDER};
    color: {SURFACE};
}}

QPushButton#secondaryButton {{
    background: {SURFACE};
    color: {PRIMARY};
    border: 1px solid {PRIMARY};
    border-radius: 8px;
    padding: 8px 18px;
    min-height: 20px;
}}

QPushButton#secondaryButton:hover {{
    background: {PRIMARY_LIGHT};
}}

QPushButton#secondaryButton:disabled {{
    color: {DISABLED};
    border-color: {BORDER};
    background: {SURFACE};
}}

QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QComboBox {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px 10px;
    selection-background-color: {PRIMARY_LIGHT};
    selection-color: {TEXT};
    min-height: 20px;
}}

QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QSpinBox:focus, QComboBox:focus {{
    border: 1px solid {PRIMARY};
}}

QListWidget {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 4px;
    outline: none;
}}

QListWidget::item {{
    padding: 8px 10px;
    border-radius: 6px;
}}

QListWidget::item:selected {{
    background: {PRIMARY_LIGHT};
    color: {TEXT};
}}

QListWidget::item:hover {{
    background: {BACKGROUND};
}}

QRadioButton, QCheckBox {{
    spacing: 8px;
}}

QRadioButton::indicator, QCheckBox::indicator {{
    width: 16px;
    height: 16px;
}}

QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: 8px;
    background: {SURFACE};
    top: -1px;
}}

QTabBar::tab {{
    background: transparent;
    color: {TEXT_SECONDARY};
    padding: 8px 14px;
    border: none;
    border-bottom: 2px solid transparent;
}}

QTabBar::tab:selected {{
    color: {PRIMARY};
    font-weight: 600;
    border-bottom: 2px solid {PRIMARY};
}}

QTabBar::tab:hover {{
    color: {TEXT};
}}

QProgressBar {{
    border: 1px solid {BORDER};
    border-radius: 6px;
    background: {SURFACE};
    text-align: center;
    color: {TEXT};
    min-height: 18px;
}}

QProgressBar::chunk {{
    background: {PRIMARY};
    border-radius: 5px;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 4px 2px;
}}

QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 4px;
    min-height: 24px;
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 2px 4px;
}}

QScrollBar::handle:horizontal {{
    background: {BORDER};
    border-radius: 4px;
    min-width: 24px;
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}

QLabel#sectionTitle, QLabel#groupTitle {{
    font-size: 14px;
    font-weight: 600;
    color: {TEXT};
}}

QLabel#thumbImage {{
    background: {PRIMARY_LIGHT};
    color: {TEXT_SECONDARY};
    border-radius: 8px;
}}

QLabel#thumbCaption {{
    color: {TEXT_SECONDARY};
    font-size: 12px;
}}

QFrame#thumbTile {{
    background: transparent;
    border: none;
}}

QLabel#busyNotice {{
    color: {PRIMARY};
    font-weight: 600;
}}

QScrollArea#pageScroll {{
    border: none;
    background: transparent;
}}

QScrollArea#pageScroll > QWidget > QWidget {{
    background: transparent;
}}

QPushButton#primaryButton:pressed {{
    background: {PRIMARY_HOVER};
}}

QPushButton#secondaryButton:pressed {{
    background: {PRIMARY_LIGHT};
}}

QMessageBox {{
    background: {SURFACE};
}}

QToolTip {{
    background: {TEXT};
    color: {SURFACE};
    border: none;
    padding: 6px 8px;
}}
"""
