"""용량·시간·해상도 변환 단위 테스트."""

from __future__ import annotations

import pytest

from core.format_utils import format_duration, format_filesize, format_fps, format_resolution


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, "0 B"),
        (1023, "1023 B"),
        (1024, "1.0 KB"),
        (1536, "1.5 KB"),
        (1048576, "1.0 MB"),
        (1024**3, "1.0 GB"),
        (1024**4, "1.0 TB"),
        (5000, "4.9 KB"),
    ],
)
def test_format_filesize_known_values(value: int, expected: str) -> None:
    assert format_filesize(value) == expected


@pytest.mark.parametrize("value", [None, -1, "100", True, False, float("nan"), float("inf")])
def test_format_filesize_invalid(value: object) -> None:
    assert format_filesize(value) == "알 수 없음"  # type: ignore[arg-type]


def test_format_filesize_float() -> None:
    assert format_filesize(2048.4) == "2.0 KB"


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (0, "00:00"),
        (59, "00:59"),
        (60, "01:00"),
        (65.9, "01:05"),
        (3599, "59:59"),
        (3600, "1:00:00"),
        (3661, "1:01:01"),
        (36000, "10:00:00"),
    ],
)
def test_format_duration_known_values(seconds: float, expected: str) -> None:
    assert format_duration(seconds) == expected


@pytest.mark.parametrize("value", [None, -1, -0.1, "60", True, float("nan"), float("inf")])
def test_format_duration_invalid(value: object) -> None:
    assert format_duration(value) == "알 수 없음"  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("height", "expected"),
    [
        (1080, "1080p"),
        (720.0, "720p"),
        (0, "-"),
        (-10, "-"),
        (None, "-"),
    ],
)
def test_format_resolution(height: object, expected: str) -> None:
    assert format_resolution(height) == expected  # type: ignore[arg-type]


def test_format_resolution_ignores_width_when_height_exists() -> None:
    assert format_resolution(1080, 1920) == "1080p"


@pytest.mark.parametrize(
    ("fps", "expected"),
    [
        (30, "30"),
        (29.97, "30"),
        (59.94, "60"),
        (23.5, "23.5"),
        (None, "-"),
        (0, "-"),
        (-1, "-"),
    ],
)
def test_format_fps(fps: object, expected: str) -> None:
    assert format_fps(fps) == expected  # type: ignore[arg-type]
