"""유튜브 영상 URL 형식 검증.

UI에 의존하지 않는다. 재생목록만 있는 주소는 거절하고,
영상 ID가 포함된 watch / youtu.be / shorts 주소만 허용한다.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")

_ALLOWED_HOSTS = frozenset(
    {
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "music.youtube.com",
        "youtu.be",
        "www.youtu.be",
    }
)


def extract_video_id(url: str) -> str | None:
    """유튜브 URL에서 11자리 영상 ID를 꺼낸다.

    지원 형식이 아니거나 ID가 없으면 None을 반환한다.
    """
    if not isinstance(url, str):
        return None
    text = url.strip()
    if not text:
        return None
    if "://" not in text:
        text = "https://" + text

    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"}:
        return None
    host = (parsed.hostname or "").lower()
    if host not in _ALLOWED_HOSTS:
        return None

    path = parsed.path or ""
    if host.endswith("youtu.be"):
        parts = [part for part in path.split("/") if part]
        if len(parts) != 1 or not _VIDEO_ID.fullmatch(parts[0]):
            return None
        return parts[0]

    shorts = re.fullmatch(r"/shorts/([A-Za-z0-9_-]{11})/?", path)
    if shorts:
        return shorts.group(1)

    if path.rstrip("/") == "/watch":
        video_ids = parse_qs(parsed.query).get("v") or []
        if not video_ids:
            return None
        video_id = video_ids[0]
        if _VIDEO_ID.fullmatch(video_id):
            return video_id
    return None


def is_valid_youtube_url(url: str) -> bool:
    """지원하는 단일 영상 URL인지 확인한다."""
    return extract_video_id(url) is not None
