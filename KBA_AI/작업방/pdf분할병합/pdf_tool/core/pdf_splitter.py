"""PDF를 열고, 분할 계획에 맞는 페이지 묶음을 만든다.

페이지 인덱스는 0부터다. 화면의 1 기반 번호 변환은 page_parser가 맡는다.
"""

from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from core.page_parser import SplitMode, format_page_span, groups_for_mode


class PdfDocumentError(Exception):
    """사용자에게 그대로 보여줄 PDF 열기/저장 오류."""


@dataclass(frozen=True)
class SplitPlan:
    """아직 저장하지 않은 분할 결과."""

    source_path: str
    source_name: str
    page_count: int
    mode: str
    expression: str
    groups: tuple[tuple[int, ...], ...]
    labels: tuple[str, ...]


def inspect_pdf(path: str) -> tuple[str, int]:
    """파일 이름과 페이지 수를 반환한다.

    Raises:
        PdfDocumentError: 없거나, 암호화됐거나, 손상된 PDF.
    """
    reader = open_reader(path)
    return Path(path).name, len(reader.pages)


def open_reader(path: str) -> PdfReader:
    """읽기 가능한 PDF 리더를 연다.

    빈 암호로 열리는 문서만 통과시킨다.
    """
    file_path = Path(path)
    if not file_path.is_file():
        raise PdfDocumentError("PDF 파일을 찾을 수 없습니다.")
    if file_path.suffix.lower() != ".pdf":
        raise PdfDocumentError("PDF 파일만 선택할 수 있습니다.")
    try:
        reader = PdfReader(str(file_path))
    except (PdfReadError, OSError, ValueError) as exc:
        raise PdfDocumentError("손상되었거나 열 수 없는 PDF입니다.") from exc
    except Exception as exc:
        raise PdfDocumentError("손상되었거나 열 수 없는 PDF입니다.") from exc

    if reader.is_encrypted:
        try:
            unlocked = reader.decrypt("")
        except Exception:
            unlocked = 0
        if not unlocked:
            raise PdfDocumentError("암호화된 PDF입니다. 암호를 해제한 뒤 다시 선택해 주세요.")

    try:
        page_count = len(reader.pages)
    except Exception as exc:
        raise PdfDocumentError("손상되었거나 열 수 없는 PDF입니다.") from exc
    if page_count < 1:
        raise PdfDocumentError("페이지가 없는 PDF입니다.")
    return reader


def build_split_plan(path: str, mode: SplitMode | str, expression: str) -> SplitPlan:
    """파일을 확인한 뒤 분할 묶음을 만든다.

    Args:
        path: 원본 PDF 경로.
        mode: 다섯 가지 분할 방식.
        expression: 해당 방식의 입력 문자열.

    Raises:
        PdfDocumentError: PDF를 열 수 없을 때.
        PageParseError: 입력값이 잘못됐을 때.
    """
    source_name, page_count = inspect_pdf(path)
    groups = groups_for_mode(mode, expression, page_count)
    resolved = mode if isinstance(mode, SplitMode) else SplitMode(mode)
    frozen = tuple(tuple(group) for group in groups)
    return SplitPlan(
        source_path=str(Path(path).resolve()),
        source_name=source_name,
        page_count=page_count,
        mode=resolved.value,
        expression=expression.strip(),
        groups=frozen,
        labels=tuple(format_page_span(group) for group in frozen),
    )
