"""yt-dlp로 선택한 포맷을 저장한다.

덮어쓰기를 고른 경우에는 임시 이름으로 받은 뒤 성공했을 때만 교체한다.
그래서 취소해도 기존 파일이 먼저 지워지지 않는다.
"""

from __future__ import annotations

import errno
import os
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadCancelled as YtDownloadCancelled
from yt_dlp.utils import DownloadError as YtDownloadError

from core.analyzer import FormatOption, find_ffmpeg
from core.format_utils import format_duration, format_filesize

_TEMP_SUFFIX = "._tmpdl"
_RESERVED_NAME = re.compile(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\.|$)", re.IGNORECASE)
_INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


class DownloadCancelled(Exception):
    """사용자가 다운로드를 취소했다."""


class UserDownloadError(Exception):
    """사용자에게 보여줄 다운로드 실패."""


@dataclass(frozen=True)
class ProgressUpdate:
    """진행률 표시에 쓰는 상태."""

    phase: str
    percent: float | None = None
    speed_text: str = ""
    eta_text: str = ""


class _QuietLogger:
    """yt-dlp 로그를 화면에 뿌리지 않는다."""

    def debug(self, message: str) -> None:
        del message

    def warning(self, message: str) -> None:
        del message

    def error(self, message: str) -> None:
        del message


def output_directory_error(path: str) -> str | None:
    """저장 폴더를 확인하고, 문제가 있으면 한글 메시지를 반환한다."""
    if not isinstance(path, str) or not path.strip():
        return "다운로드 폴더를 선택해 주세요."
    directory = Path(path)
    if not directory.exists():
        return "선택한 폴더가 존재하지 않습니다."
    if not directory.is_dir():
        return "선택한 경로가 폴더가 아닙니다."

    probe = directory / f".yt_downloader_write_test_{uuid.uuid4().hex}"
    try:
        probe.write_text("ok", encoding="utf-8")
    except OSError:
        return "선택한 폴더에 파일을 쓸 권한이 없습니다."
    try:
        probe.unlink()
    except OSError:
        pass
    return None


def sanitize_windows_stem(title: str) -> str:
    """Windows에서 파일 이름으로 쓸 수 있게 제목을 정리한다."""
    text = _INVALID_CHARS.sub("_", title or "")
    text = text.replace("%", "％")
    text = re.sub(r"\s+", " ", text).strip(" .")
    if _RESERVED_NAME.match(text):
        text = f"_{text}"
    return text or "video"


def make_filename_stem(title: str, output_dir: str, ext: str) -> str:
    """경로 길이를 넘지 않도록 자른 파일 이름 줄기를 만든다."""
    stem = sanitize_windows_stem(title)
    extra = len(_TEMP_SUFFIX) + len(ext) + 8
    budget = 240 - len(str(Path(output_dir))) - extra
    if budget < 12:
        budget = 12
    trimmed = stem[:budget].rstrip(" .")
    return trimmed or "video"


def output_file(output_dir: str, stem: str, ext: str) -> Path:
    """최종 저장 경로를 만든다."""
    return Path(output_dir) / f"{stem}.{ext}"


def numbered_stem(output_dir: str, stem: str, ext: str) -> str:
    """같은 이름이 있을 때 stem_1, stem_2 형태의 빈 이름을 찾는다."""
    directory = Path(output_dir)
    for index in range(1, 10000):
        candidate = f"{stem}_{index}"
        if not (directory / f"{candidate}.{ext}").exists():
            return candidate
    raise UserDownloadError("같은 이름의 파일이 너무 많아 번호를 붙일 수 없습니다.")


def download_media(
    url: str,
    option: FormatOption,
    output_dir: str,
    filename_stem: str,
    *,
    overwrite: bool,
    progress_callback: Callable[[ProgressUpdate], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> str:
    """선택한 포맷을 저장하고 최종 파일 경로를 반환한다."""
    folder_error = output_directory_error(output_dir)
    if folder_error:
        raise UserDownloadError(folder_error)
    ffmpeg_path = find_ffmpeg()
    if option.needs_ffmpeg and ffmpeg_path is None:
        raise UserDownloadError("FFmpeg를 찾을 수 없어 병합 또는 변환을 마치지 못했습니다.")

    directory = Path(output_dir)
    final_path = output_file(output_dir, filename_stem, option.output_ext)
    if final_path.exists() and not overwrite:
        raise UserDownloadError("같은 이름의 파일이 이미 있습니다.")

    work_stem = f"{filename_stem}{_TEMP_SUFFIX}" if overwrite else filename_stem
    if overwrite:
        _remove_prefixed(directory, work_stem)
    else:
        _cleanup_incomplete(directory, work_stem)

    def cancel_requested() -> bool:
        return bool(should_cancel and should_cancel())

    captured: dict[str, str] = {}

    def emit(update: ProgressUpdate) -> None:
        if progress_callback is not None:
            progress_callback(update)

    def raise_if_cancelled() -> None:
        if cancel_requested():
            raise YtDownloadCancelled("다운로드가 취소되었습니다.")

    def on_progress(status: dict) -> None:
        raise_if_cancelled()
        state = status.get("status")
        if state == "downloading":
            emit(_progress_from_status(status))
        elif state == "finished" and option.needs_ffmpeg:
            filename = status.get("filename")
            if isinstance(filename, str):
                captured["filename"] = filename
            emit(ProgressUpdate(phase="processing"))

    def on_postprocess(status: dict) -> None:
        raise_if_cancelled()
        state = status.get("status")
        if state in {"started", "processing", "finished"}:
            emit(ProgressUpdate(phase="processing"))
            info = status.get("info_dict") or {}
            filepath = info.get("filepath")
            if isinstance(filepath, str):
                captured["filename"] = filepath

    class _CancellableYoutubeDL(YoutubeDL):
        def urlopen(self, req):
            raise_if_cancelled()
            return super().urlopen(req)

    ydl_opts: dict = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "noplaylist": True,
        "overwrites": False,
        "windowsfilenames": True,
        "restrictfilenames": False,
        "paths": {"home": str(directory)},
        "outtmpl": f"{work_stem}.%(ext)s",
        "format": option.format_selector,
        "final_ext": option.output_ext,
        "retries": 3,
        "fragment_retries": 3,
        "socket_timeout": 30,
        "progress_hooks": [on_progress],
        "postprocessor_hooks": [on_postprocess],
        "logger": _QuietLogger(),
    }
    if ffmpeg_path:
        ydl_opts["ffmpeg_location"] = str(Path(ffmpeg_path).parent)
    if option.merge_output_format:
        ydl_opts["merge_output_format"] = option.merge_output_format
    if option.extract_audio:
        ydl_opts["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ]

    try:
        raise_if_cancelled()
        with _CancellableYoutubeDL(ydl_opts) as ydl:
            result_code = ydl.download([url])
    except YtDownloadCancelled:
        _cleanup_after_stop(directory, work_stem, remove_completed_work=overwrite)
        raise DownloadCancelled() from None
    except Exception as exc:
        _cleanup_after_stop(directory, work_stem, remove_completed_work=overwrite)
        raise UserDownloadError(classify_download_error(exc)) from exc

    if result_code not in (0, None):
        _cleanup_after_stop(directory, work_stem, remove_completed_work=overwrite)
        raise UserDownloadError("다운로드에 실패했습니다. 잠시 후 다시 시도해 주세요.")

    produced = _find_output(directory, work_stem, option.output_ext, captured.get("filename"))
    if produced is None:
        _cleanup_after_stop(directory, work_stem, remove_completed_work=True)
        raise UserDownloadError("다운로드가 끝났지만 저장된 파일을 찾지 못했습니다.")

    try:
        if produced.resolve() != final_path.resolve():
            os.replace(produced, final_path)
    except OSError as exc:
        _cleanup_after_stop(directory, work_stem, remove_completed_work=overwrite)
        raise UserDownloadError(classify_download_error(exc)) from exc

    _cleanup_incomplete(directory, work_stem)
    return str(final_path)


def classify_download_error(exc: BaseException) -> str:
    """다운로드 예외를 원인별 한글 안내 문구로 바꾼다."""
    if _has_disk_full(exc):
        return "디스크 공간이 부족합니다."
    if _has_permission(exc):
        return "선택한 폴더에 파일을 쓸 권한이 없습니다."
    text = _exception_text(exc)
    if "ffmpeg" in text or "ffprobe" in text:
        return "FFmpeg를 찾을 수 없어 병합 또는 변환을 마치지 못했습니다."
    if _looks_like_network(text):
        return "네트워크 연결이 끊어졌습니다. 인터넷 연결을 확인해 주세요."
    if isinstance(exc, YtDownloadError) and "ffmpeg" in text:
        return "FFmpeg를 찾을 수 없어 병합 또는 변환을 마치지 못했습니다."
    return "다운로드 중 알 수 없는 오류가 발생했습니다."


def _progress_from_status(status: dict) -> ProgressUpdate:
    downloaded = status.get("downloaded_bytes")
    total = status.get("total_bytes") or status.get("total_bytes_estimate")
    percent = None
    if isinstance(downloaded, (int, float)) and isinstance(total, (int, float)) and total > 0:
        percent = max(0.0, min(100.0, float(downloaded) / float(total) * 100))
    speed = status.get("speed")
    speed_text = ""
    if isinstance(speed, (int, float)) and speed > 0:
        speed_text = f"{format_filesize(speed)}/s"
    eta = status.get("eta")
    eta_text = ""
    if isinstance(eta, (int, float)) and eta >= 0:
        rendered = format_duration(eta)
        if rendered != "알 수 없음":
            eta_text = rendered
    return ProgressUpdate(phase="downloading", percent=percent, speed_text=speed_text, eta_text=eta_text)


def _find_output(directory: Path, work_stem: str, expected_ext: str, hinted: str | None) -> Path | None:
    expected = directory / f"{work_stem}.{expected_ext}"
    if expected.is_file():
        return expected
    if hinted:
        hinted_path = Path(hinted)
        if hinted_path.is_file() and not _is_partial_name(hinted_path.name):
            return hinted_path
    prefix = work_stem + "."
    candidates = [
        path
        for path in directory.iterdir()
        if path.is_file() and path.name.startswith(prefix) and not _is_partial_name(path.name) and not _is_intermediate_media(path.name, work_stem)
    ]
    preferred = [path for path in candidates if path.suffix.lower() == f".{expected_ext.lower()}"]
    pool = preferred or candidates
    if not pool:
        return None
    return max(pool, key=lambda path: path.stat().st_mtime)


def _cleanup_after_stop(directory: Path, work_stem: str, *, remove_completed_work: bool) -> None:
    if not directory.is_dir():
        return
    prefix = work_stem + "."
    for path in list(directory.iterdir()):
        if not path.is_file() or not path.name.startswith(prefix):
            continue
        if _is_partial_name(path.name) or _is_intermediate_media(path.name, work_stem) or remove_completed_work:
            _unlink(path)


def _cleanup_incomplete(directory: Path, work_stem: str) -> None:
    _cleanup_after_stop(directory, work_stem, remove_completed_work=False)


def _remove_prefixed(directory: Path, work_stem: str) -> None:
    _cleanup_after_stop(directory, work_stem, remove_completed_work=True)


def _is_partial_name(name: str) -> bool:
    """미완성 임시 파일인지 확인한다.

    덮어쓰기용 작업 이름(._tmpdl)은 완성 파일이므로 임시 파일로 보지 않는다.
    """
    lowered = name.lower()
    if ".part" in lowered or ".ytdl" in lowered or ".temp" in lowered:
        return True
    return lowered.endswith(".tmp")


def _is_intermediate_media(name: str, stem: str) -> bool:
    prefix = stem + ".f"
    if not name.startswith(prefix):
        return False
    return name[len(prefix) : len(prefix) + 1].isdigit()


def _unlink(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass


def _iter_exceptions(exc: BaseException):
    seen: set[int] = set()
    stack: list[BaseException | None] = [exc]
    while stack:
        current = stack.pop()
        if current is None or id(current) in seen:
            continue
        seen.add(id(current))
        yield current
        if current.__cause__ is not None:
            stack.append(current.__cause__)
        if current.__context__ is not None and current.__context__ is not current.__cause__:
            stack.append(current.__context__)
        exc_info = getattr(current, "exc_info", None)
        if exc_info and len(exc_info) > 1 and exc_info[1] is not None:
            stack.append(exc_info[1])


def _exception_text(exc: BaseException) -> str:
    parts = []
    for current in _iter_exceptions(exc):
        parts.append(type(current).__name__)
        parts.append(str(current))
    return "\n".join(parts).lower()


def _has_disk_full(exc: BaseException) -> bool:
    for current in _iter_exceptions(exc):
        if isinstance(current, OSError) and current.errno == errno.ENOSPC:
            return True
        if getattr(current, "winerror", None) == 112:
            return True
        text = str(current).lower()
        if "no space left" in text or "not enough space" in text or "디스크" in text and "부족" in text:
            return True
    return False


def _has_permission(exc: BaseException) -> bool:
    for current in _iter_exceptions(exc):
        if isinstance(current, OSError) and current.errno in {errno.EACCES, errno.EPERM}:
            return True
        if getattr(current, "winerror", None) in {5, 32}:
            return True
        text = str(current).lower()
        if "permission denied" in text or "액세스가 거부" in text or "access is denied" in text:
            return True
    return False


def _looks_like_network(text: str) -> bool:
    tokens = (
        "unable to download",
        "urlopen error",
        "getaddrinfo",
        "timed out",
        "timeout",
        "connection aborted",
        "connection reset",
        "connection refused",
        "temporary failure",
        "network is unreachable",
        "remote end closed",
        "transport",
    )
    return any(token in text for token in tokens)
