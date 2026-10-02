# -*- mode: python ; coding: utf-8 -*-
"""PDF 분할/병합 앱을 창 모드 실행 파일 하나로 묶는다."""

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

hiddenimports = collect_submodules("pdf2docx")
hiddenimports += [
    "fitz",
    "cv2",
    "docx",
    "PIL",
    "PyQt5.QtSvg",
    "PyQt5.QtWidgets",
    "PyQt5.QtGui",
    "PyQt5.QtCore",
]

datas = [("resources", "resources")]
datas += collect_data_files("pdf2docx")

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "torch",
        "tensorflow",
        "matplotlib",
        "pandas",
        "scipy",
        "sklearn",
        "langchain",
        "streamlit",
        "gradio",
        "notebook",
        "IPython",
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="PDF분할병합",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
