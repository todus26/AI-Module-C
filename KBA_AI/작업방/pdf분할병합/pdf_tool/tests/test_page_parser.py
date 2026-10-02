"""page_parser 정상, 경계, 오류 케이스."""

import pytest

from core.page_parser import (
    PageParseError,
    SplitMode,
    format_page_span,
    groups_for_mode,
    parse_equal_parts,
    parse_fixed_chunks,
    parse_ranges,
    parse_selected_pages,
    parse_split_after,
)


def test_selected_pages_keep_input_order() -> None:
    assert parse_selected_pages("5, 1, 3", 10) == [4, 0, 2]


def test_selected_pages_accept_fullwidth_comma() -> None:
    assert parse_selected_pages("1，3，5", 5) == [0, 2, 4]


def test_selected_pages_boundary_first_and_last() -> None:
    assert parse_selected_pages("1, 10", 10) == [0, 9]
    assert parse_selected_pages("1", 1) == [0]


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("", "입력"),
        ("   ", "입력"),
        ("1,", "형식"),
        (",1", "형식"),
        ("1,,3", "형식"),
        ("a", "형식"),
        ("1.5", "형식"),
        ("-1", "형식"),
        ("0", "범위"),
        ("11", "범위"),
        ("1, 1", "중복"),
    ],
)
def test_selected_pages_reject_bad_input(text: str, message: str) -> None:
    with pytest.raises(PageParseError, match=message):
        parse_selected_pages(text, 10)


def test_ranges_create_one_group_per_span() -> None:
    assert parse_ranges("1-3, 5-8", 10) == [
        [0, 1, 2],
        [4, 5, 6, 7],
    ]


def test_ranges_accept_tilde_and_single_page_span() -> None:
    assert parse_ranges("3~7", 10) == [[2, 3, 4, 5, 6]]
    assert parse_ranges("1-1", 1) == [[0]]


def test_ranges_keep_written_order() -> None:
    assert parse_ranges("5-6, 1-2", 6) == [[4, 5], [0, 1]]


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("", "입력"),
        ("3", "시작-끝"),
        ("1-3-5", "형식"),
        ("5-3", "클 수"),
        ("1-11", "범위"),
        ("0-2", "범위"),
        ("1-", "형식"),
        ("-3", "형식"),
    ],
)
def test_ranges_reject_bad_input(text: str, message: str) -> None:
    with pytest.raises(PageParseError, match=message):
        parse_ranges(text, 10)


def test_fixed_chunks_put_remainder_in_the_last_file() -> None:
    groups = parse_fixed_chunks("3", 10)
    assert [len(group) for group in groups] == [3, 3, 3, 1]
    assert groups[-1] == [9]


def test_fixed_chunks_boundaries() -> None:
    assert parse_fixed_chunks("1", 3) == [[0], [1], [2]]
    assert parse_fixed_chunks("10", 10) == [list(range(10))]
    assert parse_fixed_chunks("15", 10) == [list(range(10))]


@pytest.mark.parametrize("text", ["", "0", "-2", "3.5", "두 페이지"])
def test_fixed_chunks_reject_bad_input(text: str) -> None:
    with pytest.raises(PageParseError):
        parse_fixed_chunks(text, 10)


def test_split_after_cuts_following_pages_into_the_next_file() -> None:
    assert parse_split_after("4, 9", 12) == [
        [0, 1, 2, 3],
        [4, 5, 6, 7, 8],
        [9, 10, 11],
    ]


def test_split_after_sorts_and_drops_the_final_page() -> None:
    assert parse_split_after("9, 4", 12) == parse_split_after("4, 9", 12)
    assert parse_split_after("4, 12", 12) == [
        [0, 1, 2, 3],
        list(range(4, 12)),
    ]


def test_split_after_boundary_between_first_pages() -> None:
    assert parse_split_after("1", 2) == [[0], [1]]


@pytest.mark.parametrize(
    ("text", "page_count", "message"),
    [
        ("", 12, "입력"),
        ("12", 12, "나눌 위치"),
        ("4, 4", 12, "중복"),
        ("0", 12, "범위"),
        ("13", 12, "범위"),
        ("4-9", 12, "형식"),
    ],
)
def test_split_after_reject_bad_input(text: str, page_count: int, message: str) -> None:
    with pytest.raises(PageParseError, match=message):
        parse_split_after(text, page_count)


@pytest.mark.parametrize(
    ("pages", "parts", "sizes"),
    [
        (10, 3, [4, 3, 3]),
        (10, 4, [3, 3, 2, 2]),
        (10, 1, [10]),
        (10, 10, [1] * 10),
        (5, 3, [2, 2, 1]),
    ],
)
def test_equal_parts_give_remainder_to_front_files(pages: int, parts: int, sizes: list[int]) -> None:
    groups = parse_equal_parts(str(parts), pages)
    assert [len(group) for group in groups] == sizes
    assert sum(sizes) == pages
    assert all(group for group in groups)


def test_equal_parts_reject_too_many_files_and_empty() -> None:
    with pytest.raises(PageParseError, match="클 수 없습니다"):
        parse_equal_parts("11", 10)
    with pytest.raises(PageParseError, match="입력"):
        parse_equal_parts("", 10)
    with pytest.raises(PageParseError, match="정수"):
        parse_equal_parts("0", 10)


def test_groups_for_mode_wraps_page_selection_as_one_file() -> None:
    assert groups_for_mode(SplitMode.PAGES, "1, 3", 5) == [[0, 2]]
    assert groups_for_mode("chunk", "2", 4) == [[0, 1], [2, 3]]


def test_groups_for_mode_reject_unknown_mode() -> None:
    with pytest.raises(PageParseError, match="알 수 없는"):
        groups_for_mode("sideways", "1", 3)


def test_empty_document_is_rejected() -> None:
    with pytest.raises(PageParseError, match="페이지가 없는"):
        parse_selected_pages("1", 0)


def test_format_page_span_compresses_runs_without_sorting() -> None:
    assert format_page_span([0, 1, 2, 4]) == "1-3, 5"
    assert format_page_span([4, 0, 2]) == "5, 1, 3"
    assert format_page_span([0]) == "1"
    assert format_page_span([]) == ""
