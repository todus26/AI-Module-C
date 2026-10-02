"""yt-dlp로 영상 정보를 분석하고 받을 수 있는 포맷 목록을 정리한다."""

from __future__ import annotations

import os
import shutil
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from yt_dlp import YoutubeDL

from core.format_utils import format_filesize, format_fps, format_resolution

_THUMBNAIL_LIMIT = 5_000_000
_USER_AGENT = "Mozilla/5.0"


class AnalyzeError(Exception):
    """사용자에게 보여줄 분석 실패."""


@dataclass(frozen=True)
class FormatOption:
    """표의 한 줄과 다운로드에 필요한 선택 정보."""

    key: str
    category: str
    kind_label: str
    resolution_label: str
    ext: str
    fps_label: str
    codec_label: str
    filesize_label: str
    enabled: bool
    is_preset: bool
    format_selector: str
    output_ext: str
    needs_ffmpeg: bool
    disabled_reason: str = ""
    merge_output_format: str | None = None
    extract_audio: bool = False


@dataclass(frozen=True)
class VideoInfo:
    """분석이 끝난 영상 한 편."""

    video_id: str
    title: str
    channel: str
    duration_seconds: int | None
    thumbnail_bytes: bytes | None
    formats: tuple[FormatOption, ...]
    webpage_url: str


class _QuietLogger:
    """yt-dlp 로그를 화면에 뿌리지 않는다."""

    def debug(self, message: str) -> None:
        del message

    def info(self, message: str) -> None:
        del message

    def warning(self, message: str) -> None:
        del message

    def error(self, message: str) -> None:
        del message


def find_ffmpeg() -> str | None:
    """ffmpeg 실행 파일 경로를 찾는다. 없으면 None.

    이미 켜져 있던 터미널은 winget이 바꾼 PATH를 아직 모를 수 있다.
    그럴 때는 Windows 사용자/시스템 PATH 레지스트리도 확인한다.
    """
    found = shutil.which("ffmpeg")
    if found:
        return found
    if os.name != "nt":
        return None
    for directory in _windows_registry_path_dirs():
        candidate = Path(directory) / "ffmpeg.exe"
        if candidate.is_file():
            return str(candidate)
    return None


def is_ffmpeg_available() -> bool:
    """시스템에 ffmpeg 실행 파일이 있는지 확인한다."""
    return find_ffmpeg() is not None


def _windows_registry_path_dirs() -> list[str]:
    """현재 프로세스 PATH가 아니라 레지스트리에 저장된 PATH 목록을 읽는다."""
    import winreg

    locations = (
        (winreg.HKEY_CURRENT_USER, r"Environment"),
        (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
    )
    directories: list[str] = []
    for hive, key_path in locations:
        try:
            with winreg.OpenKey(hive, key_path) as key:
                raw_value, _ = winreg.QueryValueEx(key, "Path")
        except OSError:
            continue
        if not isinstance(raw_value, str):
            continue
        for part in raw_value.split(";"):
            expanded = os.path.expandvars(part.strip().strip('"'))
            if expanded:
                directories.append(expanded)
    return directories


def analyze_url(url: str, *, ffmpeg_available: bool | None = None) -> VideoInfo:
    """링크를 분석해 영상 정보와 포맷 목록을 반환한다.

    네트워크와 yt-dlp 호출은 이 함수 안에서만 일어나고, 실패하면 AnalyzeError를 던진다.
    """
    if ffmpeg_available is None:
        ffmpeg_available = is_ffmpeg_available()

    options = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "noplaylist": True,
        "skip_download": True,
        "socket_timeout": 20,
        "extractor_retries": 2,
        "logger": _QuietLogger(),
    }
    try:
        with YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:
        raise AnalyzeError(classify_analyze_error(exc)) from exc

    if not isinstance(info, dict):
        raise AnalyzeError("영상을 분석하지 못했습니다. 링크를 다시 확인해 주세요.")
    if info.get("_type") in {"playlist", "multi_video"} or (
        info.get("entries") is not None and not info.get("formats")
    ):
        raise AnalyzeError("재생목록 링크입니다. 영상 하나의 링크를 입력해 주세요.")

    title = str(info.get("title") or "제목 없음")
    channel = str(info.get("channel") or info.get("uploader") or "채널 정보 없음")
    duration = info.get("duration")
    duration_seconds = int(duration) if isinstance(duration, (int, float)) and duration >= 0 else None
    formats = build_format_options(info.get("formats") or [], ffmpeg_available=ffmpeg_available)
    return VideoInfo(
        video_id=str(info.get("id") or ""),
        title=title,
        channel=channel,
        duration_seconds=duration_seconds,
        thumbnail_bytes=_load_thumbnail(info),
        formats=tuple(formats),
        webpage_url=str(info.get("webpage_url") or url),
    )


def build_format_options(raw_formats: list[dict], *, ffmpeg_available: bool) -> list[FormatOption]:
    """원본 포맷 목록을 추천 프리셋, 영상, 음원 순으로 정리한다.

    같은 해상도·확장자는 품질이 더 높은 항목 하나만 남긴다.
    """
    videos, audios = _unique_formats(raw_formats)
    options = [
        *_preset_options(videos, audios, ffmpeg_available),
        *_video_options(videos, audios, ffmpeg_available),
        *_audio_options(audios),
    ]
    return options


def classify_analyze_error(exc: BaseException) -> str:
    """예외를 원인별 한글 안내 문구로 바꾼다."""
    text = _exception_text(exc)
    if any(token in text for token in ("confirm your age", "age-restricted", "age restricted", "inappropriate for some users")):
        return "연령 제한 영상은 이 앱에서 분석할 수 없습니다."
    if any(
        token in text
        for token in (
            "private video",
            "video is private",
            "has been removed",
            "removed by the uploader",
            "account associated with this video has been terminated",
            "copyright",
            "in your country",
            "geo restricted",
            "georestricted",
            "blocked it in your country",
        )
    ):
        return "비공개이거나 삭제되었거나, 지역 제한으로 볼 수 없는 영상입니다."
    if any(
        token in text
        for token in (
            "video unavailable",
            "this video is unavailable",
            "does not exist",
            "incomplete youtube id",
            "unsupported url",
            "not a valid url",
            "invalid url",
        )
    ):
        return "올바르지 않은 링크이거나 존재하지 않는 영상입니다."
    if _looks_like_network(text):
        return "네트워크에 연결할 수 없습니다. 인터넷 연결을 확인해 주세요."
    return "알 수 없는 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."


def _preset_options(
    videos: list[dict],
    audios: list[dict],
    ffmpeg_available: bool,
) -> list[FormatOption]:
    best_video = _best(videos, _video_rank)
    best_audio = _best([*audios, *[item for item in videos if _has_audio(item)]], _audio_rank)
    m4a = _best(
        [item for item in audios if (item.get("ext") or "").lower() == "m4a"],
        _audio_rank,
    )

    best_height = format_resolution((best_video or {}).get("height")) if best_video else "최고"
    if best_height == "-":
        best_height = "최고"
    best_fps = format_fps((best_video or {}).get("fps")) if best_video else "-"
    merged_size = _sum_sizes(best_video, best_audio if best_video and not _has_audio(best_video) else None)

    best_mp4 = _option(
        key="preset-best-mp4",
        category="preset",
        kind_label="최고 화질 영상 (mp4)",
        resolution_label=best_height,
        ext="mp4",
        fps_label=best_fps,
        codec_label="자동 병합",
        filesize=merged_size,
        enabled=ffmpeg_available,
        is_preset=True,
        format_selector="bestvideo+bestaudio/best",
        output_ext="mp4",
        needs_ffmpeg=True,
        disabled_reason="" if ffmpeg_available else "FFmpeg가 없어 병합할 수 없습니다.",
        merge_output_format="mp4",
    )
    mp3 = _option(
        key="preset-mp3",
        category="preset",
        kind_label="음원만 (mp3)",
        resolution_label="-",
        ext="mp3",
        fps_label="-",
        codec_label="mp3",
        filesize=_filesize(best_audio) if best_audio else None,
        enabled=ffmpeg_available,
        is_preset=True,
        format_selector="bestaudio/best",
        output_ext="mp3",
        needs_ffmpeg=True,
        disabled_reason="" if ffmpeg_available else "FFmpeg가 없어 MP3로 변환할 수 없습니다.",
        extract_audio=True,
    )
    if m4a is None:
        m4a_option = _option(
            key="preset-m4a",
            category="preset",
            kind_label="음원만 (m4a)",
            resolution_label="-",
            ext="m4a",
            fps_label="-",
            codec_label="aac",
            filesize=None,
            enabled=False,
            is_preset=True,
            format_selector="bestaudio[ext=m4a]/bestaudio",
            output_ext="m4a",
            needs_ffmpeg=False,
            disabled_reason="m4a 음원을 찾지 못했습니다.",
        )
    else:
        m4a_option = _option(
            key="preset-m4a",
            category="preset",
            kind_label="음원만 (m4a)",
            resolution_label="-",
            ext="m4a",
            fps_label="-",
            codec_label=_short_codec(m4a.get("acodec")),
            filesize=_filesize(m4a),
            enabled=True,
            is_preset=True,
            format_selector=str(m4a.get("format_id")),
            output_ext="m4a",
            needs_ffmpeg=False,
        )
    return [best_mp4, mp3, m4a_option]


def _video_options(
    videos: list[dict],
    audios: list[dict],
    ffmpeg_available: bool,
) -> list[FormatOption]:
    ordered = sorted(videos, key=_video_sort_key, reverse=True)
    options: list[FormatOption] = []
    for fmt in ordered:
        has_audio = _has_audio(fmt)
        container = (fmt.get("ext") or "mp4").lower()
        if has_audio:
            output_ext = container
            merge_format = None
            needs_ffmpeg = False
            selector = str(fmt.get("format_id"))
            size = _filesize(fmt)
            kind = "영상+음성"
            codec = f"{_short_codec(fmt.get('vcodec'))} + {_short_codec(fmt.get('acodec'))}"
        else:
            output_ext = _merged_container(fmt)
            merge_format = output_ext
            needs_ffmpeg = True
            selector = f"{fmt.get('format_id')}+bestaudio"
            size = _sum_sizes(fmt, _best(audios, _audio_rank))
            kind = "영상만"
            codec = _short_codec(fmt.get("vcodec"))
        enabled = ffmpeg_available or not needs_ffmpeg
        options.append(
            _option(
                key=f"video-{fmt.get('format_id')}",
                category="video",
                kind_label=kind,
                resolution_label=format_resolution(fmt.get("height")),
                ext=output_ext,
                fps_label=format_fps(fmt.get("fps")),
                codec_label=codec,
                filesize=size,
                enabled=enabled,
                is_preset=False,
                format_selector=selector,
                output_ext=output_ext,
                needs_ffmpeg=needs_ffmpeg,
                disabled_reason="" if enabled else "FFmpeg가 없어 음성과 병합할 수 없습니다.",
                merge_output_format=merge_format,
            )
        )
    return options


def _audio_options(audios: list[dict]) -> list[FormatOption]:
    ordered = sorted(audios, key=_audio_sort_key, reverse=True)
    options: list[FormatOption] = []
    for fmt in ordered:
        ext = (fmt.get("ext") or "m4a").lower()
        options.append(
            _option(
                key=f"audio-{fmt.get('format_id')}",
                category="audio",
                kind_label="음성만",
                resolution_label="-",
                ext=ext,
                fps_label="-",
                codec_label=_short_codec(fmt.get("acodec")),
                filesize=_filesize(fmt),
                enabled=True,
                is_preset=False,
                format_selector=str(fmt.get("format_id")),
                output_ext=ext,
                needs_ffmpeg=False,
            )
        )
    return options


def _option(
    *,
    key: str,
    category: str,
    kind_label: str,
    resolution_label: str,
    ext: str,
    fps_label: str,
    codec_label: str,
    filesize: int | None,
    enabled: bool,
    is_preset: bool,
    format_selector: str,
    output_ext: str,
    needs_ffmpeg: bool,
    disabled_reason: str = "",
    merge_output_format: str | None = None,
    extract_audio: bool = False,
) -> FormatOption:
    return FormatOption(
        key=key,
        category=category,
        kind_label=kind_label,
        resolution_label=resolution_label,
        ext=ext,
        fps_label=fps_label,
        codec_label=codec_label,
        filesize_label=format_filesize(filesize),
        enabled=enabled,
        is_preset=is_preset,
        format_selector=format_selector,
        output_ext=output_ext,
        needs_ffmpeg=needs_ffmpeg,
        disabled_reason=disabled_reason,
        merge_output_format=merge_output_format,
        extract_audio=extract_audio,
    )


def _unique_formats(raw_formats: list[dict]) -> tuple[list[dict], list[dict]]:
    videos: dict[tuple, dict] = {}
    audios: dict[str, dict] = {}
    for fmt in raw_formats:
        if not isinstance(fmt, dict) or _is_storyboard(fmt) or fmt.get("has_drm"):
            continue
        format_id = str(fmt.get("format_id") or "")
        if not format_id:
            continue
        ext = str(fmt.get("ext") or "").lower()
        if ext in {"mhtml", "jpg", "png", "webp"}:
            continue
        has_video = _has_video(fmt)
        has_audio = _has_audio(fmt)
        if not has_video and not has_audio:
            continue
        quality = _quality_key(fmt)
        if has_video:
            height = int(fmt.get("height") or 0)
            kind = "muxed" if has_audio else "video"
            key = (kind, height, ext)
            current = videos.get(key)
            if current is None or quality > _quality_key(current):
                videos[key] = fmt
        else:
            current = audios.get(ext)
            if current is None or quality > _quality_key(current):
                audios[ext] = fmt
    return list(videos.values()), list(audios.values())


def _is_storyboard(fmt: dict) -> bool:
    format_id = str(fmt.get("format_id") or "")
    note = str(fmt.get("format_note") or "").lower()
    return format_id.startswith("sb") or "storyboard" in note


def _has_video(fmt: dict) -> bool:
    codec = fmt.get("vcodec")
    return bool(codec) and codec != "none"


def _has_audio(fmt: dict) -> bool:
    codec = fmt.get("acodec")
    return bool(codec) and codec != "none"


def _filesize(fmt: dict | None) -> int | None:
    if not fmt:
        return None
    size = fmt.get("filesize")
    if size is None:
        size = fmt.get("filesize_approx")
    if isinstance(size, bool) or not isinstance(size, (int, float)):
        return None
    if size < 0:
        return None
    return int(size)


def _sum_sizes(video: dict | None, audio: dict | None) -> int | None:
    video_size = _filesize(video)
    audio_size = _filesize(audio)
    if video_size is None:
        return audio_size
    if audio_size is None:
        return video_size
    return video_size + audio_size


def _quality_key(fmt: dict) -> tuple:
    protocol = str(fmt.get("protocol") or "")
    if protocol in {"https", "http"}:
        protocol_score = 2
    elif "m3u8" in protocol:
        protocol_score = 0
    else:
        protocol_score = 1
    return (
        float(fmt.get("tbr") or 0),
        _filesize(fmt) or 0,
        float(fmt.get("fps") or 0),
        float(fmt.get("abr") or 0),
        protocol_score,
    )


def _video_rank(fmt: dict) -> tuple:
    return (
        int(fmt.get("height") or 0),
        float(fmt.get("tbr") or 0),
        _filesize(fmt) or 0,
        float(fmt.get("fps") or 0),
    )


def _audio_rank(fmt: dict) -> tuple:
    return (float(fmt.get("abr") or 0), float(fmt.get("tbr") or 0), _filesize(fmt) or 0)


def _video_sort_key(fmt: dict) -> tuple:
    return (int(fmt.get("height") or 0), 1 if _has_audio(fmt) else 0, _filesize(fmt) or 0)


def _audio_sort_key(fmt: dict) -> tuple:
    return (float(fmt.get("abr") or 0), _filesize(fmt) or 0)


def _best(formats: list[dict], key) -> dict | None:
    if not formats:
        return None
    return max(formats, key=key)


def _short_codec(codec: object) -> str:
    if not isinstance(codec, str) or not codec or codec == "none":
        return "-"
    return codec.split(".")[0]


def _merged_container(fmt: dict) -> str:
    """영상만 있는 스트림을 음성과 합칠 때 쓸 컨테이너."""
    ext = str(fmt.get("ext") or "").lower()
    codec = _short_codec(fmt.get("vcodec"))
    if ext == "mp4" and codec in {"avc1", "avc", "h264", "hev1", "hvc1"}:
        return "mp4"
    return "mkv"


def _load_thumbnail(info: dict) -> bytes | None:
    candidates: list[str] = []
    primary = info.get("thumbnail")
    if isinstance(primary, str):
        candidates.append(primary)
    for thumb in info.get("thumbnails") or []:
        if isinstance(thumb, dict) and isinstance(thumb.get("url"), str):
            url = thumb["url"]
            if url not in candidates:
                candidates.append(url)
    ordered = candidates[:1] + list(reversed(candidates[1:]))
    for url in ordered[:4]:
        data = _fetch_thumbnail(url)
        if data:
            return data
    return None


def _fetch_thumbnail(url: str) -> bytes | None:
    if not url.startswith(("http://", "https://")):
        return None
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            data = response.read(_THUMBNAIL_LIMIT + 1)
    except (OSError, urllib.error.URLError, TimeoutError, ValueError):
        return None
    if not data or len(data) > _THUMBNAIL_LIMIT:
        return None
    return data


def _exception_text(exc: BaseException) -> str:
    parts: list[str] = []
    seen: set[int] = set()
    stack: list[BaseException | None] = [exc]
    while stack:
        current = stack.pop()
        if current is None or id(current) in seen:
            continue
        seen.add(id(current))
        parts.append(type(current).__name__)
        parts.append(str(current))
        if current.__cause__ is not None:
            stack.append(current.__cause__)
        if current.__context__ is not None and current.__context__ is not current.__cause__:
            stack.append(current.__context__)
        exc_info = getattr(current, "exc_info", None)
        if exc_info and len(exc_info) > 1 and exc_info[1] is not None:
            stack.append(exc_info[1])
    return "\n".join(parts).lower()


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
        "name or service not known",
        "network is unreachable",
        "nodename nor servname",
        "urlerror",
        "remote end closed",
    )
    return any(token in text for token in tokens)
