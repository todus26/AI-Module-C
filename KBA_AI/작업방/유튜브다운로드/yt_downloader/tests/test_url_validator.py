"""유튜브 URL 검증 단위 테스트."""

from __future__ import annotations

import pytest

from core.url_validator import extract_video_id, is_valid_youtube_url

VIDEO_ID = "dQw4w9WgXcQ"


@pytest.mark.parametrize(
    "url",
    [
        f"https://www.youtube.com/watch?v={VIDEO_ID}",
        f"http://youtube.com/watch?v={VIDEO_ID}",
        f"https://m.youtube.com/watch?v={VIDEO_ID}&list=PL123",
        f"https://music.youtube.com/watch?v={VIDEO_ID}",
        f"https://www.youtube.com/watch?app=desktop&v={VIDEO_ID}",
        f"HTTPS://WWW.YOUTUBE.COM/watch?v={VIDEO_ID}",
        f"https://youtu.be/{VIDEO_ID}",
        f"https://www.youtu.be/{VIDEO_ID}?t=43",
        f"https://www.youtube.com/shorts/{VIDEO_ID}",
        f"https://m.youtube.com/shorts/{VIDEO_ID}?feature=share",
        f"  youtube.com/watch?v={VIDEO_ID}  ",
        f"youtu.be/{VIDEO_ID}",
    ],
)
def test_valid_urls(url: str) -> None:
    assert is_valid_youtube_url(url) is True
    assert extract_video_id(url) == VIDEO_ID


@pytest.mark.parametrize(
    "url",
    [
        "",
        "   ",
        "https://youtube.com",
        "https://www.youtube.com/playlist?list=PL123",
        "https://www.youtube.com/watch?list=PL123",
        "https://www.youtube.com/watch?v=",
        "https://www.youtube.com/watch?v=short",
        "https://www.youtube.com/watch?v=dQw4w9WgXcQq",
        "https://youtu.be/",
        "https://youtu.be/dQw4w9WgXc",
        "https://youtu.be/dQw4w9WgXcQ/extra",
        "https://www.youtube.com/shorts/",
        "https://www.youtube.com/shorts/dQw4w9WgXcQ/extra",
        "https://www.youtube.com/embed/dQw4w9WgXcQ",
        "https://vimeo.com/123456",
        "https://youtube.com.evil.com/watch?v=dQw4w9WgXcQ",
        "https://notyoutube.com/watch?v=dQw4w9WgXcQ",
        "javascript:alert(1)",
        "ftp://youtube.com/watch?v=dQw4w9WgXcQ",
    ],
)
def test_invalid_urls(url: str) -> None:
    assert is_valid_youtube_url(url) is False
    assert extract_video_id(url) is None


@pytest.mark.parametrize("value", [None, 123, b"https://youtu.be/dQw4w9WgXcQ", ["url"]])
def test_non_string_input(value: object) -> None:
    assert is_valid_youtube_url(value) is False  # type: ignore[arg-type]
    assert extract_video_id(value) is None  # type: ignore[arg-type]


def test_video_id_length_boundary() -> None:
    ten = "a" * 10
    eleven = "abc_DEF-012"
    twelve = "a" * 12
    assert len(eleven) == 11
    assert extract_video_id(f"https://youtu.be/{ten}") is None
    assert extract_video_id(f"https://youtu.be/{eleven}") == eleven
    assert extract_video_id(f"https://www.youtube.com/shorts/{twelve}") is None
