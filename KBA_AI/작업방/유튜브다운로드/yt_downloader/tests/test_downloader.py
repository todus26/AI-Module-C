"""파일 이름, 폴더 검사, 다운로드 오류 문구 테스트."""

from __future__ import annotations

import errno

from core.downloader import (
    _is_partial_name,
    classify_download_error,
    make_filename_stem,
    numbered_stem,
    output_directory_error,
    output_file,
    sanitize_windows_stem,
)


def test_sanitize_windows_stem() -> None:
    assert sanitize_windows_stem('a<b>:c') == "a_b__c"
    assert sanitize_windows_stem("CON") == "_CON"
    assert sanitize_windows_stem("  ...  ") == "video"
    assert sanitize_windows_stem("100%") == "100％"
    assert sanitize_windows_stem("테스트:영상") == "테스트_영상"
    assert sanitize_windows_stem("") == "video"


def test_make_filename_stem_uses_sanitized_title(tmp_path) -> None:
    stem = make_filename_stem("테스트:영상", str(tmp_path), "mp4")
    assert stem == "테스트_영상"


def test_numbered_stem_skips_existing_files(tmp_path) -> None:
    (tmp_path / "영상.mp4").write_text("a", encoding="utf-8")
    (tmp_path / "영상_1.mp4").write_text("b", encoding="utf-8")
    assert numbered_stem(str(tmp_path), "영상", "mp4") == "영상_2"
    assert output_file(str(tmp_path), "영상_2", "mp4") == tmp_path / "영상_2.mp4"


def test_output_directory_error(tmp_path) -> None:
    assert output_directory_error(str(tmp_path)) is None
    missing = tmp_path / "없는폴더"
    assert output_directory_error(str(missing)) == "선택한 폴더가 존재하지 않습니다."
    file_path = tmp_path / "파일.txt"
    file_path.write_text("x", encoding="utf-8")
    assert output_directory_error(str(file_path)) == "선택한 경로가 폴더가 아닙니다."
    assert output_directory_error("") == "다운로드 폴더를 선택해 주세요."


def test_partial_name_keeps_overwrite_work_file() -> None:
    assert _is_partial_name("영상._tmpdl.mp4") is False
    assert _is_partial_name("영상.mp4.part") is True
    assert _is_partial_name("영상.f137.mp4.part") is True
    assert _is_partial_name("영상.mp4.ytdl") is True


def test_classify_download_error() -> None:
    assert classify_download_error(OSError(errno.ENOSPC, "No space left on device")) == "디스크 공간이 부족합니다."
    assert classify_download_error(OSError(errno.EACCES, "Permission denied")) == "선택한 폴더에 파일을 쓸 권한이 없습니다."
    assert "FFmpeg" in classify_download_error(RuntimeError("ffprobe and ffmpeg not found"))
    assert "네트워크" in classify_download_error(RuntimeError("Unable to download webpage: timed out"))
    assert "알 수 없는" in classify_download_error(RuntimeError("boom"))
