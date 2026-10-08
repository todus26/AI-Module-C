"""Excel 로드, 컬럼 매핑, 거래처 단위 테이블 구성."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

import config


class DataLoadError(Exception):
    def __init__(self, message: str, file_name: str | None = None, columns: list[str] | None = None):
        super().__init__(message)
        self.file_name = file_name
        self.columns = columns or []


@dataclass
class DatasetBundle:
    info: pd.DataFrame
    meeting: pd.DataFrame
    news: pd.DataFrame
    sales: pd.DataFrame
    customers: pd.DataFrame
    file_mtimes: dict[str, datetime]


def normalize_key(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip()
    text = text.replace("(주)", "").replace("㈜", "").replace("주식회사", "")
    text = re.sub(r"\s+", "", text)
    return text.casefold()


def file_mtimes(data_dir: Path | None = None) -> dict[str, float]:
    data_dir = data_dir or config.DATA_DIR
    stamps: dict[str, float] = {}
    for key, filename in config.DATA_FILES.items():
        path = data_dir / filename
        stamps[key] = path.stat().st_mtime if path.exists() else -1.0
    return stamps


def _read_excel(data_dir: Path, kind: str) -> pd.DataFrame:
    filename = config.DATA_FILES[kind]
    path = data_dir / filename
    if not path.exists():
        raise DataLoadError(
            f"데이터를 불러오지 못했습니다. 파일이 없습니다: {filename}",
            file_name=filename,
        )
    sheet = config.SHEETS[kind]
    try:
        xl = pd.ExcelFile(path)
    except Exception as exc:
        raise DataLoadError(f"{filename}을 열 수 없습니다: {exc}", file_name=filename) from exc
    if sheet not in xl.sheet_names:
        raise DataLoadError(
            f"{filename}에 시트 '{sheet}'가 없습니다. 있는 시트: {xl.sheet_names}",
            file_name=filename,
        )
    return pd.read_excel(path, sheet_name=sheet)


def _rename(df: pd.DataFrame, kind: str, file_name: str) -> pd.DataFrame:
    mapping = config.COLUMN_MAP[kind]
    missing = [src for src in mapping.values() if src not in df.columns]
    if missing:
        raise DataLoadError(
            f"데이터를 불러오지 못했습니다. 파일명과 컬럼을 확인하세요. "
            f"{file_name}에 없는 컬럼: {missing}. 실제 컬럼: {list(df.columns)}",
            file_name=file_name,
            columns=missing,
        )
    renamed = df.rename(columns={src: std for std, src in mapping.items()})
    keep = list(mapping.keys())
    out = renamed[keep].copy()
    out["join_key"] = out[config.JOIN_KEY].map(normalize_key)
    return out


def _valid_location(lat: object, lon: object) -> bool:
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (TypeError, ValueError):
        return False
    if pd.isna(lat_f) or pd.isna(lon_f):
        return False
    if lat_f == 0 and lon_f == 0:
        return False
    return config.LAT_MIN <= lat_f <= config.LAT_MAX and config.LON_MIN <= lon_f <= config.LON_MAX


def _parse_dates(df: pd.DataFrame, column: str) -> pd.DataFrame:
    out = df.copy()
    out[column] = pd.to_datetime(out[column], errors="coerce")
    return out


def _latest_meeting(meeting: pd.DataFrame) -> pd.DataFrame:
    if meeting.empty:
        return pd.DataFrame(columns=["join_key", "latest_meeting_date"])
    ordered = meeting.dropna(subset=["meeting_date"]).sort_values("meeting_date")
    latest = ordered.groupby("join_key", as_index=False).tail(1)
    return latest[["join_key", "meeting_date"]].rename(columns={"meeting_date": "latest_meeting_date"})


def _sales_summary(sales: pd.DataFrame) -> pd.DataFrame:
    if sales.empty:
        return pd.DataFrame(
            columns=["join_key", "first_sales_date", "latest_sales_date", "latest_sales_amount"]
        )
    ordered = sales.dropna(subset=["sales_date"]).sort_values("sales_date")
    first = ordered.groupby("join_key", as_index=False)["sales_date"].min().rename(
        columns={"sales_date": "first_sales_date"}
    )
    latest = ordered.groupby("join_key", as_index=False).tail(1)[
        ["join_key", "sales_date", "amount_thousand_krw"]
    ].rename(columns={"sales_date": "latest_sales_date", "amount_thousand_krw": "latest_sales_amount"})
    return first.merge(latest, on="join_key", how="outer")


def build_customers(info: pd.DataFrame, meeting: pd.DataFrame, sales: pd.DataFrame) -> pd.DataFrame:
    customers = info.copy()
    customers = customers.merge(_latest_meeting(meeting), on="join_key", how="left")
    customers = customers.merge(_sales_summary(sales), on="join_key", how="left")
    customers["has_location"] = [
        _valid_location(lat, lon) for lat, lon in zip(customers["latitude"], customers["longitude"])
    ]
    if "status" not in customers.columns:
        customers["status"] = "일반"
    if "status_reason" not in customers.columns:
        customers["status_reason"] = ""
    return customers


def load_all(data_dir: Path | None = None) -> DatasetBundle:
    data_dir = Path(data_dir or config.DATA_DIR)
    raw = {}
    parsed = {}
    mtimes: dict[str, datetime] = {}
    date_cols = {
        "meeting": "meeting_date",
        "news": "news_date",
        "sales": "sales_date",
    }
    for kind in ("info", "meeting", "news", "sales"):
        filename = config.DATA_FILES[kind]
        path = data_dir / filename
        mtimes[kind] = datetime.fromtimestamp(path.stat().st_mtime) if path.exists() else datetime.min
        raw[kind] = _read_excel(data_dir, kind)
        parsed[kind] = _rename(raw[kind], kind, filename)
        if kind in date_cols:
            parsed[kind] = _parse_dates(parsed[kind], date_cols[kind])
            parsed[kind] = parsed[kind][parsed[kind]["join_key"] != ""].copy()
        if kind == "info":
            parsed[kind] = parsed[kind][parsed[kind]["join_key"] != ""].copy()
            parsed[kind] = parsed[kind].drop_duplicates(subset=["join_key"], keep="first")
        if kind == "sales":
            parsed[kind]["amount_thousand_krw"] = pd.to_numeric(
                parsed[kind]["amount_thousand_krw"], errors="coerce"
            )
            parsed[kind]["quantity_ton"] = pd.to_numeric(parsed[kind]["quantity_ton"], errors="coerce")

    customers = build_customers(parsed["info"], parsed["meeting"], parsed["sales"])
    return DatasetBundle(
        info=parsed["info"],
        meeting=parsed["meeting"],
        news=parsed["news"],
        sales=parsed["sales"],
        customers=customers,
        file_mtimes=mtimes,
    )
