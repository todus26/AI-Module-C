"""PDF 열기, 분할, 병합, 저장이 페이지 수를 지키는지 확인한다."""

from pathlib import Path

import pytest
from pypdf import PdfWriter

from core.exporter import (
    ConflictPolicy,
    PageRef,
    dedupe_stems,
    part_from_merge,
    parts_from_split,
    resolve_conflict,
    stem_for_group,
    write_docx,
    write_pdf,
)
from core.page_parser import SplitMode
from core.pdf_merger import MergeItem, build_merge_plan
from core.pdf_splitter import PdfDocumentError, build_split_plan, inspect_pdf
from core.thumbnail import render_pages


def _blank_pdf(path: Path, pages: int) -> None:
    writer = PdfWriter()
    for _index in range(pages):
        writer.add_blank_page(width=200, height=280)
    with path.open("wb") as handle:
        writer.write(handle)


def test_split_plan_and_written_pdf_keep_requested_pages(tmp_path: Path) -> None:
    source = tmp_path / "보고서.pdf"
    _blank_pdf(source, 10)
    plan = build_split_plan(str(source), SplitMode.CHUNK, "3")
    assert [len(group) for group in plan.groups] == [3, 3, 3, 1]

    parts = parts_from_split(plan.source_name, plan.source_path, plan.groups, plan.labels)
    output = tmp_path / "part.pdf"
    write_pdf(parts[0].pages, output)
    assert inspect_pdf(str(output))[1] == 3


def test_merge_duplicate_file_keeps_every_copy(tmp_path: Path) -> None:
    source = tmp_path / "same.pdf"
    _blank_pdf(source, 2)
    name, count = inspect_pdf(str(source))
    plan = build_merge_plan(
        [
            MergeItem(str(source), name, count),
            MergeItem(str(source), name, count),
        ]
    )
    assert plan.total_pages == 4
    part = part_from_merge([(item.path, item.page_count) for item in plan.items], 2, "test")
    output = tmp_path / "merged.pdf"
    write_pdf(part.pages, output)
    assert inspect_pdf(str(output))[1] == 4


def test_encrypted_and_damaged_pdf_raise_korean_errors(tmp_path: Path) -> None:
    encrypted = tmp_path / "locked.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.encrypt("secret")
    with encrypted.open("wb") as handle:
        writer.write(handle)
    with pytest.raises(PdfDocumentError, match="암호화"):
        inspect_pdf(str(encrypted))

    damaged = tmp_path / "broken.pdf"
    damaged.write_bytes(b"this is not a pdf")
    with pytest.raises(PdfDocumentError, match="손상"):
        inspect_pdf(str(damaged))

    missing = tmp_path / "missing.pdf"
    with pytest.raises(PdfDocumentError, match="찾을 수 없습니다"):
        inspect_pdf(str(missing))


def test_thumbnail_png_and_conflict_names(tmp_path: Path) -> None:
    source = tmp_path / "preview.pdf"
    _blank_pdf(source, 1)
    images = render_pages(str(source), [0])
    assert images[0] is not None
    assert images[0][:8] == b"\x89PNG\r\n\x1a\n"

    assert stem_for_group("보고서", 1, "1-3, 5") == "보고서_part1_1-3_5"
    assert dedupe_stems(["a", "a", "b"]) == ["a", "a_1", "b"]

    existing = tmp_path / "out.pdf"
    existing.write_bytes(b"x")
    numbered = resolve_conflict(existing, ConflictPolicy.AUTONUMBER)
    assert numbered.name == "out_1.pdf"
    assert resolve_conflict(existing, ConflictPolicy.OVERWRITE) == existing


def test_merge_requires_two_files(tmp_path: Path) -> None:
    source = tmp_path / "one.pdf"
    _blank_pdf(source, 1)
    name, count = inspect_pdf(str(source))
    with pytest.raises(PdfDocumentError, match="두 개 이상"):
        build_merge_plan([MergeItem(str(source), name, count)])


def test_write_docx_creates_word_file(tmp_path: Path) -> None:
    source = tmp_path / "page.pdf"
    _blank_pdf(source, 1)
    output = tmp_path / "page.docx"
    write_docx((PageRef(str(source.resolve()), 0),), output)
    assert output.exists()
    assert output.stat().st_size > 0
