"""용량, 재생 시간, 해상도, FPS를 화면에 보여줄 문자열로 바꾼다."""

from __future__ import annotations

import math

_SIZE_UNITS = ("B", "KB", "MB", "GB", "TB")


def format_filesize(num_bytes: int | float | None) -> str:
    """바이트 크기를 읽기 쉬운 문자열로 변환한다.

    값이 없거나 숫자가 아니면 '알 수 없음'을 반환한다.
    """
    if isinstance(num_bytes, bool) or not isinstance(num_bytes, (int, float)):
        return "알 수 없음"
    if not math.isfinite(num_bytes) or num_bytes < 0:
        return "알 수 없음"

    size = float(num_bytes)
    unit = _SIZE_UNITS[0]
    for unit in _SIZE_UNITS:
        if size < 1024 or unit == _SIZE_UNITS[-1]:
            break
        size /= 1024
    if unit == "B":
        return f"{int(size)} B"
    return f"{size:.1f} {unit}"


def format_duration(seconds: int | float | None) -> str:
    """초 단위 길이를 MM:SS 또는 H:MM:SS 문자열로 변환한다.

    소수 초는 내림한다. 값이 없으면 '알 수 없음'을 반환한다.
    """
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)):
        return "알 수 없음"
    if not math.isfinite(seconds) or seconds < 0:
        return "알 수 없음"

    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_resolution(height: int | float | None, width: int | float | None = None) -> str:
    """영상 높이를 1080p 형태의 해상도 문자열로 변환한다."""
    del width  # 높이가 있을 때는 높이만 사용한다.
    if isinstance(height, bool) or not isinstance(height, (int, float)):
        return "-"
    if not math.isfinite(height) or height <= 0:
        return "-"
    return f"{int(height)}p"


def format_fps(fps: int | float | None) -> str:
    """프레임 수를 표에 넣을 문자열로 변환한다."""
    if isinstance(fps, bool) or not isinstance(fps, (int, float)):
        return "-"
    if not math.isfinite(fps) or fps <= 0:
        return "-"
    rounded = round(fps)
    if abs(fps - rounded) < 0.1:
        return str(int(rounded))
    return f"{fps:.1f}"
