"""거래처 상태(신규, 일반, 위험) 분류."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

import pandas as pd

import config

logger = logging.getLogger(__name__)


def reference_date() -> date:
    if config.REFERENCE_DATE:
        value = config.REFERENCE_DATE
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        return pd.to_datetime(value).date()
    return date.today()


def _to_date(value: object) -> date | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.date()


def _skipped_rules() -> list[str]:
    skipped: list[str] = []
    if not config.NEW_CUSTOMER_DAYS:
        skipped.append("NEW_CUSTOMER_DAYS")
    if not config.SALES_DECLINE_RULE:
        skipped.append("SALES_DECLINE_RULE")
    if not config.REPEAT_REQUEST_RULE:
        skipped.append("REPEAT_REQUEST_RULE")
    if skipped:
        logger.info("상태 판정에서 제외된 조건: %s", ", ".join(skipped))
    return skipped


def _is_new(first_sales_date: object, today: date) -> tuple[bool, str]:
    days = config.NEW_CUSTOMER_DAYS
    if not days:
        return False, ""
    started = _to_date(first_sales_date)
    if started is None:
        return False, ""
    if (today - started).days <= int(days):
        return True, f"거래 시작 후 {days}일 이내 (첫 납품일 {started.isoformat()})"
    return False, ""


def _sales_windows(sales: pd.DataFrame, join_key: str, today: date) -> tuple[float, float]:
    rule = config.SALES_DECLINE_RULE or {}
    recent_months = int(rule.get("recent_months", 0) or 0)
    previous_months = int(rule.get("previous_months", 0) or 0)
    if recent_months <= 0 or previous_months <= 0:
        return 0.0, 0.0
    subset = sales[sales["join_key"] == join_key].copy()
    if subset.empty:
        return 0.0, 0.0
    subset["sales_date"] = pd.to_datetime(subset["sales_date"], errors="coerce")
    subset = subset.dropna(subset=["sales_date"])
    end = pd.Timestamp(today)
    recent_start = end - pd.DateOffset(months=recent_months)
    prev_start = recent_start - pd.DateOffset(months=previous_months)
    recent = subset[(subset["sales_date"] > recent_start) & (subset["sales_date"] <= end)]
    previous = subset[(subset["sales_date"] > prev_start) & (subset["sales_date"] <= recent_start)]
    return float(recent["amount_thousand_krw"].sum()), float(previous["amount_thousand_krw"].sum())


def _is_sales_decline(sales: pd.DataFrame, join_key: str, today: date) -> tuple[bool, str]:
    rule = config.SALES_DECLINE_RULE
    if not rule:
        return False, ""
    rate = float(rule.get("decline_rate") or 0)
    recent_months = int(rule.get("recent_months") or 0)
    previous_months = int(rule.get("previous_months") or 0)
    if rate <= 0 or recent_months <= 0 or previous_months <= 0:
        return False, ""
    recent_sum, previous_sum = _sales_windows(sales, join_key, today)
    if previous_sum <= 0:
        return False, ""
    drop = (previous_sum - recent_sum) / previous_sum
    if drop >= rate:
        pct = drop * 100
        return True, (
            f"최근 {recent_months}개월 매출이 직전 {previous_months}개월 대비 {pct:.0f}% 감소"
        )
    return False, ""


def _is_repeat_request(meeting: pd.DataFrame, join_key: str, today: date) -> tuple[bool, str]:
    rule = config.REPEAT_REQUEST_RULE
    if not rule:
        return False, ""
    window_days = int(rule.get("window_days") or 0)
    min_count = int(rule.get("min_count") or 0)
    if window_days <= 0 or min_count <= 0:
        return False, ""
    subset = meeting[meeting["join_key"] == join_key].copy()
    if subset.empty or "request" not in subset.columns:
        return False, ""
    subset["meeting_date"] = pd.to_datetime(subset["meeting_date"], errors="coerce")
    start = pd.Timestamp(today - timedelta(days=window_days))
    recent = subset[subset["meeting_date"] >= start]
    counts = (
        recent["request"]
        .dropna()
        .astype(str)
        .str.strip()
        .replace("", pd.NA)
        .dropna()
        .value_counts()
    )
    repeated = counts[counts >= min_count]
    if repeated.empty:
        return False, ""
    text, count = repeated.index[0], int(repeated.iloc[0])
    short = text if len(text) <= 40 else text[:40] + "..."
    return True, f"최근 {window_days}일 내 동일 요청 {count}회 ({short})"


def classify_row(
    row: pd.Series,
    sales: pd.DataFrame,
    meeting: pd.DataFrame,
    today: date,
) -> tuple[str, str]:
    reasons: list[str] = []
    risk = False
    is_new = False

    declined, decline_reason = _is_sales_decline(sales, row["join_key"], today)
    if declined:
        risk = True
        reasons.append(decline_reason)

    repeated, repeat_reason = _is_repeat_request(meeting, row["join_key"], today)
    if repeated:
        risk = True
        reasons.append(repeat_reason)

    new_flag, new_reason = _is_new(row.get("first_sales_date"), today)
    if new_flag:
        is_new = True
        reasons.append(new_reason)

    if risk:
        return "위험", " / ".join(reasons)
    if is_new:
        return "신규", " / ".join(reasons) if reasons else new_reason
    if reasons:
        return "일반", " / ".join(reasons)
    skipped = []
    if not config.NEW_CUSTOMER_DAYS:
        skipped.append("신규 기간")
    if not config.SALES_DECLINE_RULE:
        skipped.append("구매 감소")
    if not config.REPEAT_REQUEST_RULE:
        skipped.append("반복 요청")
    if skipped and not (config.NEW_CUSTOMER_DAYS or config.SALES_DECLINE_RULE or config.REPEAT_REQUEST_RULE):
        return "일반", "신규·위험 판정 조건이 설정되지 않음"
    return "일반", "위험·신규 신호 없음"


def apply_status(
    customers: pd.DataFrame,
    sales: pd.DataFrame,
    meeting: pd.DataFrame,
) -> pd.DataFrame:
    _skipped_rules()
    today = reference_date()
    out = customers.copy()
    statuses: list[str] = []
    reasons: list[str] = []
    for _, row in out.iterrows():
        status, reason = classify_row(row, sales, meeting, today)
        statuses.append(status)
        reasons.append(reason)
    out["status"] = statuses
    out["status_reason"] = reasons
    return _apply_demo_new(out)


def _apply_demo_new(customers: pd.DataFrame) -> pd.DataFrame:
    names = [str(name).strip() for name in (config.DEMO_NEW_CUSTOMERS or []) if str(name).strip()]
    if not names:
        return customers
    mask = customers["customer_name"].astype(str).isin(names) & (customers["status"] != "위험")
    if not mask.any():
        return customers
    out = customers.copy()
    out.loc[mask, "status"] = "신규"
    out.loc[mask, "status_reason"] = "임시 시연: 신규 거래처로 표시"
    return out


def status_counts(customers: pd.DataFrame) -> dict[str, int]:
    counts = customers["status"].value_counts().to_dict()
    return {label: int(counts.get(label, 0)) for label in config.STATUS_ORDER}


def condition_counts(
    customers: pd.DataFrame,
    sales: pd.DataFrame,
    meeting: pd.DataFrame,
) -> dict[str, int]:
    today = reference_date()
    new_n = decline_n = repeat_n = 0
    for _, row in customers.iterrows():
        if _is_new(row.get("first_sales_date"), today)[0]:
            new_n += 1
        if _is_sales_decline(sales, row["join_key"], today)[0]:
            decline_n += 1
        if _is_repeat_request(meeting, row["join_key"], today)[0]:
            repeat_n += 1
    return {
        "신규 조건": new_n,
        "구매 감소 조건": decline_n,
        "반복 요청 조건": repeat_n,
    }
