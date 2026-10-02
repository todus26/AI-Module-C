"""분할/병합 결과를 PDF 또는 Word로 저장한다."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import re
import tempfile

from pypdf import PdfReader, PdfWriter

from core.pdf_splitter import PdfDocumentError, open_reader


class ConflictPolicy(str, Enum):
    """같은 이름의 파일이 있을 때 처리 방법."""

    OVERWRITE = "overwrite"
    AUTONUMBER = "autonumber"


@dataclass(frozen=True)
class PageRef:
    """결과 파일에 넣을 페이지. index는 0부터."""

    path: str
    index: int


@dataclass(frozen=True)
class ExportPart:
    """저장 전 결과 파일 하나."""

    suggested_stem: str
    pages: tuple[PageRef, ...]


def parts_from_split(
    source_name: str,
    source_path: str,
    groups: Sequence[Sequence[int]],
    labels: Sequence[str],
) -> tuple[ExportPart, ...]:
    """분할 묶음마다 저장용 파일 정보를 만든다."""
    source_stem = _trim_stem(Path(source_name).stem or "split")
    parts: list[ExportPart] = []
    for index, (group, label) in enumerate(zip(groups, labels), start=1):
        pages = tuple(PageRef(source_path, page) for page in group)
        parts.append(ExportPart(stem_for_group(source_stem, index, label), pages))
    return tuple(parts)


def part_from_merge(items: Sequence[tuple[str, int]], file_count: int, stamp: str) -> ExportPart:
    """병합 목록 전체를 하나의 결과 파일로 만든다.

    Args:
        items: ``(경로, 페이지 수)`` 목록. 순서가 병합 순서다.
        file_count: 파일 이름에 쓸 개수.
        stamp: 같은 초에 여러 번 병합해도 이름이 겹치지 않게 하는 접미사.
    """
    pages: list[PageRef] = []
    for path, page_count in items:
        for index in range(page_count):
            pages.append(PageRef(path, index))
    return ExportPart(f"병합_{file_count}개_{stamp}", tuple(pages))


def stem_for_group(source_stem: str, index: int, label: str) -> str:
    """결과 파일의 확장자 없는 이름을 만든다."""
    token = re.sub(r"[^0-9A-Za-z가-힣-]+", "_", label).strip("_") or "pages"
    stem = f"{_trim_stem(source_stem)}_part{index}_{token}"
    if len(stem) > 80:
        return f"{_trim_stem(source_stem)}_part{index}"
    return stem


def dedupe_stems(stems: Sequence[str]) -> list[str]:
    """한 번에 저장하는 이름끼리 겹치지 않게 번호를 붙인다."""
    seen: dict[str, int] = {}
    unique: list[str] = []
    for stem in stems:
        count = seen.get(stem, 0)
        seen[stem] = count + 1
        unique.append(stem if count == 0 else f"{stem}_{count}")
    return unique


def resolve_conflict(path: Path, policy: ConflictPolicy) -> Path:
    """기존 파일을 덮어쓰거나 ``_1``, ``_2`` 이름을 고른다."""
    if not path.exists() or policy is ConflictPolicy.OVERWRITE:
        return path
    number = 1
    while number <= 9999:
        candidate = path.with_name(f"{path.stem}_{number}{path.suffix}")
        if not candidate.exists():
            return candidate
        number += 1
    raise PdfDocumentError("파일 이름을 더 이상 만들 수 없습니다.")


def write_pdf(pages: Sequence[PageRef], dest: Path) -> None:
    """여러 원본의 페이지를 순서대로 하나의 PDF로 쓴다."""
    if not pages:
        raise PdfDocumentError("저장할 페이지가 없습니다.")
    readers: dict[str, PdfReader] = {}
    writer = PdfWriter()
    try:
        for page in pages:
            reader = readers.get(page.path)
            if reader is None:
                reader = open_reader(page.path)
                readers[page.path] = reader
            # 같은 파일을 두 번 병합해도 페이지 객체가 겹치지 않게 복제한다.
            writer.add_page(reader.pages[page.index])
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("wb") as handle:
            writer.write(handle)
    except PdfDocumentError:
        raise
    except PermissionError as exc:
        raise PdfDocumentError(
            f"파일을 저장할 수 없습니다. 다른 프로그램에서 사용 중인지 확인해 주세요.\n{dest.name}"
        ) from exc
    except Exception as exc:
        raise PdfDocumentError(f"PDF를 저장하지 못했습니다. {exc}") from exc
    finally:
        for reader in readers.values():
            try:
                reader.close()
            except Exception:
                continue


def write_docx(pages: Sequence[PageRef], dest: Path) -> None:
    """페이지를 임시 PDF로 만든 뒤 Word 문서로 변환한다."""
    try:
        from pdf2docx import Converter
    except ImportError as exc:
        raise PdfDocumentError("Word 변환 라이브러리(pdf2docx)가 설치되어 있지 않습니다.") from exc

    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="pdf_tool_") as folder:
        temp_pdf = Path(folder) / "part.pdf"
        write_pdf(pages, temp_pdf)
        converter = Converter(str(temp_pdf))
        try:
            converter.convert(str(dest))
        except PermissionError as exc:
            _remove_partial(dest)
            raise PdfDocumentError(
                f"파일을 저장할 수 없습니다. 다른 프로그램에서 사용 중인지 확인해 주세요.\n{dest.name}"
            ) from exc
        except Exception as exc:
            _remove_partial(dest)
            raise PdfDocumentError(f"Word 파일로 변환하지 못했습니다. {exc}") from exc
        finally:
            converter.close()


def export_files(
    jobs: Sequence[tuple[Sequence[PageRef], Path]],
    kind: str,
    progress: Callable[[int, int, str], None] | None = None,
) -> list[Path]:
    """준비된 경로에 PDF 또는 Word 파일을 순서대로 저장한다.

    Args:
        jobs: ``(페이지 목록, 저장 경로)``.
        kind: ``pdf`` 또는 ``docx``.
        progress: ``(현재 완료 수, 전체 수, 메시지)`` 를 받는 콜백.
    """
    if kind not in {"pdf", "docx"}:
        raise PdfDocumentError("저장 형식은 PDF 또는 Word만 선택할 수 있습니다.")
    if not jobs:
        raise PdfDocumentError("저장할 파일이 없습니다.")

    written: list[Path] = []
    total = len(jobs)
    for index, (pages, dest) in enumerate(jobs, start=1):
        if progress:
            progress(index - 1, total, f"{dest.name} 저장 중 ({index}/{total})")
        if kind == "docx":
            write_docx(pages, dest)
        else:
            write_pdf(pages, dest)
        written.append(dest)
        if progress:
            progress(index, total, f"{dest.name} 저장 완료 ({index}/{total})")
    return written


def _trim_stem(stem: str) -> str:
    cleaned = re.sub(r"[^\w가-힣.-]+", "_", stem, flags=re.UNICODE).strip("._")
    return (cleaned or "document")[:40]


def _remove_partial(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
    except OSError:
        return
