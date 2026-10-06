from __future__ import annotations

from datetime import date, datetime

EXPIRING_DAYS = 3

STATUS_NORMAL = "정상"
STATUS_EXPIRING = "임박"
STATUS_EXPIRED = "만료"
STATUS_NONE = "기한 없음"


def parse_expiry(text: str | None) -> date | None:
    """YYYY-MM-DD 문자열을 날짜로 바꾼다. 빈 문자열은 기한 없음(None)이다."""
    if text is None or not str(text).strip():
        return None
    try:
        return datetime.strptime(str(text).strip(), "%Y-%m-%d").date()
    except ValueError:
        raise ValueError("유통기한은 YYYY-MM-DD 형식으로 입력하세요. (예: 2026-10-12)") from None


def days_left(expiry: date | None, today: date) -> int | None:
    if expiry is None:
        return None
    return (expiry - today).days


def expiry_status(expiry: date | None, today: date) -> str:
    left = days_left(expiry, today)
    if left is None:
        return STATUS_NONE
    if left < 0:
        return STATUS_EXPIRED
    if left <= EXPIRING_DAYS:
        return STATUS_EXPIRING
    return STATUS_NORMAL


def status_label(expiry: date | None, today: date) -> str:
    """화면에 보여줄 상태 문구. 예: '임박 (D-2)', '만료 (3일 지남)'."""
    status = expiry_status(expiry, today)
    left = days_left(expiry, today)
    if status == STATUS_EXPIRING:
        return "임박 (D-day)" if left == 0 else f"임박 (D-{left})"
    if status == STATUS_EXPIRED:
        return f"만료 ({-left}일 지남)"
    return status
