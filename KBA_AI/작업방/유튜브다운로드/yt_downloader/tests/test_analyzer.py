"""포맷 정리와 분석 오류 문구 테스트."""

from __future__ import annotations

from core.analyzer import build_format_options, classify_analyze_error

RAW_FORMATS = [
    {
        "format_id": "18",
        "ext": "mp4",
        "vcodec": "avc1.4d401e",
        "acodec": "mp4a.40.2",
        "height": 360,
        "fps": 30,
        "tbr": 500,
        "filesize": 1000,
        "protocol": "https",
    },
    {
        "format_id": "22",
        "ext": "mp4",
        "vcodec": "avc1.64001F",
        "acodec": "mp4a.40.2",
        "height": 720,
        "fps": 30,
        "tbr": 800,
        "filesize": 5000,
        "protocol": "https",
    },
    {
        "format_id": "137",
        "ext": "mp4",
        "vcodec": "avc1.640028",
        "acodec": "none",
        "height": 1080,
        "fps": 30,
        "tbr": 2500,
        "filesize": 9000,
        "protocol": "https",
    },
    {
        "format_id": "137b",
        "ext": "mp4",
        "vcodec": "avc1.640028",
        "acodec": "none",
        "height": 1080,
        "fps": 30,
        "tbr": 2000,
        "filesize": 8000,
        "protocol": "https",
    },
    {
        "format_id": "140",
        "ext": "m4a",
        "vcodec": "none",
        "acodec": "mp4a.40.2",
        "abr": 128,
        "filesize": 2000,
        "protocol": "https",
    },
    {
        "format_id": "251",
        "ext": "webm",
        "vcodec": "none",
        "acodec": "opus",
        "abr": 160,
        "filesize": 1800,
        "protocol": "https",
    },
    {
        "format_id": "sb0",
        "ext": "mhtml",
        "vcodec": "none",
        "acodec": "none",
        "format_note": "storyboard",
    },
]


def test_format_order_and_dedup() -> None:
    options = build_format_options(RAW_FORMATS, ffmpeg_available=True)
    categories = [item.category for item in options]
    assert categories[:3] == ["preset", "preset", "preset"]
    assert categories[3:6] == ["video", "video", "video"]
    assert categories[6:] == ["audio", "audio"]

    assert options[0].kind_label == "최고 화질 영상 (mp4)"
    assert options[1].kind_label == "음원만 (mp3)"
    assert options[2].kind_label == "음원만 (m4a)"
    assert [item.kind_label for item in options if item.category == "video"] == [
        "영상만",
        "영상+음성",
        "영상+음성",
    ]
    assert options[3].format_selector == "137+bestaudio"
    assert all("137b" not in item.format_selector for item in options)
    assert [item.ext for item in options if item.category == "audio"] == ["webm", "m4a"]
    assert options[3].filesize_label == "10.5 KB"
    assert options[2].filesize_label == "2.0 KB"


def test_missing_filesize_label() -> None:
    options = build_format_options(
        [
            {
                "format_id": "18",
                "ext": "mp4",
                "vcodec": "avc1",
                "acodec": "mp4a",
                "height": 360,
                "protocol": "https",
            }
        ],
        ffmpeg_available=True,
    )
    muxed = next(item for item in options if item.kind_label == "영상+음성")
    assert muxed.filesize_label == "알 수 없음"


def test_ffmpeg_disables_merge_and_mp3() -> None:
    options = build_format_options(RAW_FORMATS, ffmpeg_available=False)
    by_label = {item.kind_label: item for item in options if item.is_preset}
    assert by_label["최고 화질 영상 (mp4)"].enabled is False
    assert by_label["음원만 (mp3)"].enabled is False
    assert by_label["음원만 (m4a)"].enabled is True
    video_only = next(item for item in options if item.kind_label == "영상만")
    muxed = next(item for item in options if item.kind_label == "영상+음성")
    audio = next(item for item in options if item.kind_label == "음성만")
    assert video_only.enabled is False
    assert video_only.needs_ffmpeg is True
    assert muxed.enabled is True
    assert audio.enabled is True


def test_m4a_preset_disabled_when_missing() -> None:
    options = build_format_options(
        [
            {
                "format_id": "251",
                "ext": "webm",
                "vcodec": "none",
                "acodec": "opus",
                "abr": 160,
                "protocol": "https",
            }
        ],
        ffmpeg_available=True,
    )
    m4a = next(item for item in options if item.kind_label == "음원만 (m4a)")
    assert m4a.enabled is False
    assert "m4a" in m4a.disabled_reason


def test_classify_analyze_error() -> None:
    assert "연령" in classify_analyze_error(RuntimeError("Sign in to confirm your age"))
    assert "비공개" in classify_analyze_error(RuntimeError("Private video. Sign in if you've been granted access"))
    assert "지역" in classify_analyze_error(
        RuntimeError("The uploader has not made this video available in your country")
    )
    assert "삭제" in classify_analyze_error(RuntimeError("This video has been removed by the uploader"))
    assert "존재하지" in classify_analyze_error(RuntimeError("Video unavailable"))
    assert "네트워크" in classify_analyze_error(RuntimeError("Unable to download webpage: getaddrinfo failed"))
    assert "알 수 없는" in classify_analyze_error(RuntimeError("unexpected boom"))
