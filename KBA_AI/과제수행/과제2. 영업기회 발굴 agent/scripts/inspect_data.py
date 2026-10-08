"""data/ 엑셀 파일의 컬럼, 행 수, 결측, 샘플을 출력한다."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import DATA_DIR, DATA_FILES  # noqa: E402


def _print_frame(path: Path, sheet: str, df: pd.DataFrame) -> None:
    print(f"--- sheet: {sheet}  rows={len(df)}  cols={len(df.columns)}")
    print("COLUMNS:")
    for col in df.columns:
        null_pct = float(df[col].isna().mean() * 100)
        unique = int(df[col].nunique(dropna=True))
        print(f"  - {col}  dtype={df[col].dtype}  null={null_pct:.1f}%  unique={unique}")
    print("SAMPLE 3:")
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 160)
    pd.set_option("display.max_colwidth", 60)
    print(df.head(3).to_string(index=False))
    print()


def inspect_file(filename: str) -> None:
    path = DATA_DIR / filename
    print("=" * 80)
    if not path.exists():
        print(f"FILE: {filename}  MISSING")
        print()
        return
    xl = pd.ExcelFile(path)
    print(f"FILE: {filename}  size={path.stat().st_size}  sheets={xl.sheet_names}")
    for sheet in xl.sheet_names:
        df = pd.read_excel(path, sheet_name=sheet)
        _print_frame(path, sheet, df)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    for filename in DATA_FILES.values():
        inspect_file(filename)


if __name__ == "__main__":
    main()
