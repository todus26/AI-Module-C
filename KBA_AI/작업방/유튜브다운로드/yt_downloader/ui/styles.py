"""앱 전체 색과 QSS."""

from __future__ import annotations

PRIMARY = "#2F5D8C"
PRIMARY_HOVER = "#264E77"
PRIMARY_LIGHT = "#E8EFF7"
BACKGROUND = "#F7F9FC"
BORDER = "#D5DEE9"
TEXT = "#1F2A37"
ERROR = "#C0392B"
WHITE = "#FFFFFF"
MUTED = "#5C6B7A"
DISABLED_TEXT = "#9AA8B5"
SELECTION = "#D9E6F4"


def build_stylesheet() -> str:
    """창과 대화상자에 적용할 스타일시트를 만든다."""
    return f"""
    QMainWindow, QWidget#root {{
        background: {BACKGROUND};
        color: {TEXT};
        font-family: "Malgun Gothic", "맑은 고딕", sans-serif;
        font-size: 13px;
    }}
    QLabel {{
        background: transparent;
        color: {TEXT};
    }}
    QLabel#appTitle {{
        color: {PRIMARY};
        font-size: 22px;
        font-weight: 700;
    }}
    QLabel#ffmpegBanner {{
        background: {PRIMARY_LIGHT};
        color: {PRIMARY};
        border: 1px solid {BORDER};
        border-radius: 8px;
        padding: 10px 12px;
    }}
    QLabel#errorLabel {{
        color: {ERROR};
        font-size: 12px;
    }}
    QLabel#hintLabel, QLabel#videoMeta {{
        color: {MUTED};
    }}
    QLabel#videoTitle {{
        font-size: 15px;
        font-weight: 700;
    }}
    QLabel#thumbnail {{
        background: {PRIMARY_LIGHT};
        color: {MUTED};
        border-radius: 6px;
    }}
    QLabel#statusLabel[level="error"] {{
        color: {ERROR};
    }}
    QLabel#statusLabel[level="success"] {{
        color: {PRIMARY};
        font-weight: 600;
    }}
    QLabel#progressLabel {{
        color: {MUTED};
    }}
    QFrame#videoCard {{
        background: {WHITE};
        border: 1px solid {BORDER};
        border-radius: 10px;
    }}
    QLineEdit {{
        background: {WHITE};
        color: {TEXT};
        border: 1px solid {BORDER};
        border-radius: 8px;
        padding: 0 12px;
        min-height: 36px;
        max-height: 36px;
        selection-background-color: {PRIMARY_LIGHT};
        selection-color: {TEXT};
    }}
    QLineEdit:focus {{
        border: 1px solid {PRIMARY};
    }}
    QLineEdit:read-only {{
        background: #F4F7FB;
    }}
    QLineEdit[invalid="true"] {{
        border: 1px solid {ERROR};
    }}
    QPushButton {{
        border-radius: 8px;
        padding: 0 16px;
        min-height: 36px;
        font-weight: 600;
    }}
    QPushButton#analyzeButton, QPushButton#downloadButton {{
        background: {PRIMARY};
        color: {WHITE};
        border: none;
    }}
    QPushButton#analyzeButton:hover, QPushButton#downloadButton:hover {{
        background: {PRIMARY_HOVER};
    }}
    QPushButton#analyzeButton:pressed, QPushButton#downloadButton:pressed {{
        background: #1E4064;
    }}
    QPushButton#analyzeButton:disabled, QPushButton#downloadButton:disabled {{
        background: #B7C6D8;
        color: {BACKGROUND};
    }}
    QPushButton#folderButton, QPushButton#cancelButton, QPushButton#openFolderButton {{
        background: {WHITE};
        color: {PRIMARY};
        border: 1px solid {PRIMARY};
    }}
    QPushButton#folderButton:hover, QPushButton#cancelButton:hover, QPushButton#openFolderButton:hover {{
        background: {PRIMARY_LIGHT};
    }}
    QPushButton#folderButton:disabled, QPushButton#cancelButton:disabled, QPushButton#openFolderButton:disabled {{
        color: {DISABLED_TEXT};
        border-color: {BORDER};
        background: {BACKGROUND};
    }}
    QPushButton#refreshButton {{
        background: transparent;
        border: 1px solid {BORDER};
        border-radius: 6px;
        padding: 0px;
        margin: 0px;
        min-width: 30px;
        max-width: 30px;
        min-height: 30px;
        max-height: 30px;
    }}
    QPushButton#refreshButton:hover {{
        background: {PRIMARY_LIGHT};
    }}
    QPushButton#refreshButton:pressed {{
        background: #D5E3F2;
    }}
    QPushButton#refreshButton:disabled {{
        background: transparent;
        border-color: #E6EDF5;
    }}
    QTableWidget {{
        background: {WHITE};
        alternate-background-color: {WHITE};
        border: 1px solid {BORDER};
        border-radius: 8px;
        gridline-color: #E6EDF5;
        selection-background-color: {SELECTION};
        selection-color: {TEXT};
        outline: none;
    }}
    QTableWidget::item {{
        padding: 6px 8px;
        border: none;
        color: {TEXT};
    }}
    QTableWidget::item:selected {{
        background: {SELECTION};
        color: {TEXT};
    }}
    QHeaderView::section {{
        background: {PRIMARY_LIGHT};
        color: {TEXT};
        border: none;
        border-bottom: 1px solid {BORDER};
        padding: 8px;
        font-weight: 600;
    }}
    QProgressBar {{
        background: {PRIMARY_LIGHT};
        border: none;
        border-radius: 5px;
        min-height: 10px;
        max-height: 10px;
        text-align: center;
    }}
    QProgressBar::chunk {{
        background: {PRIMARY};
        border-radius: 5px;
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 10px;
        margin: 4px 2px 4px 0;
    }}
    QScrollBar::handle:vertical {{
        background: {BORDER};
        border-radius: 4px;
        min-height: 24px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    QToolTip {{
        background: {WHITE};
        color: {TEXT};
        border: 1px solid {BORDER};
        padding: 4px 6px;
    }}
    QMessageBox {{
        background: {WHITE};
    }}
    QMessageBox QLabel {{
        color: {TEXT};
        font-size: 13px;
    }}
    QMessageBox QPushButton {{
        min-width: 88px;
        background: {WHITE};
        color: {PRIMARY};
        border: 1px solid {PRIMARY};
    }}
    QMessageBox QPushButton:hover {{
        background: {PRIMARY_LIGHT};
    }}
    """
