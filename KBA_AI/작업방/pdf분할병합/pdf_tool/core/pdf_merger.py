"""여러 PDF를 순서대로 잇는 병합 계획을 만든다."""

from dataclasses import dataclass

from core.pdf_splitter import PdfDocumentError, inspect_pdf


@dataclass(frozen=True)
class MergeItem:
    """병합 목록의 파일 하나. 같은 경로가 여러 번 있을 수 있다."""

    path: str
    name: str
    page_count: int


@dataclass(frozen=True)
class MergePlan:
    """아직 저장하지 않은 병합 결과."""

    items: tuple[MergeItem, ...]

    @property
    def total_pages(self) -> int:
        """병합 후 전체 페이지 수."""
        return sum(item.page_count for item in self.items)


def build_merge_plan(items: list[MergeItem]) -> MergePlan:
    """목록 순서대로 다시 열어 병합 계획을 확정한다.

    Raises:
        PdfDocumentError: 파일이 두 개 미만이거나 열 수 없을 때.
    """
    if len(items) < 2:
        raise PdfDocumentError("병합하려면 PDF를 두 개 이상 선택해 주세요.")

    checked: list[MergeItem] = []
    for item in items:
        name, page_count = inspect_pdf(item.path)
        checked.append(MergeItem(path=item.path, name=name, page_count=page_count))
    return MergePlan(items=tuple(checked))
