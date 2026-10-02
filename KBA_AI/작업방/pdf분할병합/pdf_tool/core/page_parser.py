"""페이지 입력 문자열을 검증하고 0 기반 페이지 묶음으로 바꾼다.

사용자에게 보이는 페이지 번호는 1부터 시작한다.
이 모듈은 파일을 열지 않고, PyQt에도 의존하지 않는다.
"""

from enum import Enum
import re


class SplitMode(str, Enum):
    """분할 화면의 다섯 가지 입력 방식."""

    PAGES = "pages"
    RANGES = "ranges"
    CHUNK = "chunk"
    SPLIT_AT = "split_at"
    EQUAL = "equal"

    @property
    def label(self) -> str:
        """화면에 보여줄 방식 이름."""
        labels = {
            SplitMode.PAGES: "페이지 입력",
            SplitMode.RANGES: "범위 입력",
            SplitMode.CHUNK: "고정 페이지 분할",
            SplitMode.SPLIT_AT: "특정 페이지 기준 분할",
            SplitMode.EQUAL: "균등 분할",
        }
        return labels[self]


class PageParseError(ValueError):
    """입력값이 비었거나 형식·범위가 잘못됐을 때 발생한다."""


def normalize_expression(text: str) -> str:
    """사용자가 섞어 쓸 수 있는 구분자만 통일한다.

    ``~`` 와 전각 쉼표는 각각 하이픈, 쉼표로 바꾼다.
    """
    cleaned = text.replace("～", "~").replace("~", "-")
    cleaned = cleaned.replace("–", "-").replace("−", "-")
    cleaned = cleaned.replace("，", ",").replace("、", ",")
    return cleaned.strip()


def parse_selected_pages(text: str, page_count: int) -> list[int]:
    """쉼표로 구분한 페이지를 입력 순서대로 추출한다.

    Args:
        text: ``1, 3, 5`` 형식.
        page_count: 문서의 전체 페이지 수.

    Returns:
        0 기반 페이지 인덱스. 하나의 결과 파일에 들어간다.
    """
    _require_document(page_count)
    tokens = _split_csv(normalize_expression(text), "페이지 번호를 입력해 주세요.", "1, 3, 5")
    selected: list[int] = []
    seen: set[int] = set()
    for token in tokens:
        number = _parse_page_number(token, page_count)
        if number in seen:
            raise PageParseError(f"{number}페이지가 중복되었습니다.")
        seen.add(number)
        selected.append(number - 1)
    return selected


def parse_ranges(text: str, page_count: int) -> list[list[int]]:
    """범위마다 별도의 페이지 묶음을 만든다.

    Args:
        text: ``3-7`` 또는 ``1-3, 5-8``. ``~`` 도 하이픈으로 인정한다.
        page_count: 문서의 전체 페이지 수.

    Returns:
        범위 순서 그대로의 0 기반 페이지 묶음.
    """
    _require_document(page_count)
    tokens = _split_csv(normalize_expression(text), "범위를 입력해 주세요.", "1-3, 5-8")
    groups: list[list[int]] = []
    for token in tokens:
        if "-" not in token:
            raise PageParseError(f"범위는 시작-끝 형식이어야 합니다: {token}")
        left, right, *extra = token.split("-")
        if extra or not left.strip() or not right.strip():
            raise PageParseError(f"범위 형식이 올바르지 않습니다: {token}")
        start = _parse_page_number(left.strip(), page_count)
        end = _parse_page_number(right.strip(), page_count)
        if start > end:
            raise PageParseError(f"시작 페이지가 끝 페이지보다 클 수 없습니다: {token.strip()}")
        groups.append(list(range(start - 1, end)))
    return groups


def parse_fixed_chunks(text: str, page_count: int) -> list[list[int]]:
    """N페이지씩 앞에서부터 자른다.

    마지막 묶음은 N장보다 적어도 된다.
    """
    _require_document(page_count)
    size = _parse_positive_int(normalize_expression(text), "나눌 페이지 수를 입력해 주세요.")
    groups: list[list[int]] = []
    for start in range(0, page_count, size):
        groups.append(list(range(start, min(start + size, page_count))))
    return groups


def parse_split_after(text: str, page_count: int) -> list[list[int]]:
    """지정한 페이지 바로 뒤에서 문서를 나눈다.

    ``4, 9`` 이고 전체 12페이지이면 ``1-4 / 5-9 / 10-12`` 가 된다.
    순서가 뒤섞여 있어도 페이지 번호 순으로 자른다.
    마지막 페이지는 뒤에 남은 페이지가 없으므로 자르는 위치에서 뺀다.
    """
    _require_document(page_count)
    tokens = _split_csv(normalize_expression(text), "나눌 페이지를 입력해 주세요.", "4, 9")
    numbers: list[int] = []
    seen: set[int] = set()
    for token in tokens:
        number = _parse_page_number(token, page_count)
        if number in seen:
            raise PageParseError(f"{number}페이지가 중복되었습니다.")
        seen.add(number)
        numbers.append(number)

    cuts = sorted(number for number in numbers if number < page_count)
    if not cuts:
        raise PageParseError("나눌 위치가 없습니다. 마지막 페이지가 아닌 페이지를 입력해 주세요.")

    groups: list[list[int]] = []
    start = 1
    for cut in cuts:
        groups.append(list(range(start - 1, cut)))
        start = cut + 1
    if start <= page_count:
        groups.append(list(range(start - 1, page_count)))
    return groups


def parse_equal_parts(text: str, page_count: int) -> list[list[int]]:
    """전체를 N개 파일로 나누고, 나머지는 앞 파일부터 1페이지씩 더한다.

    예: 10페이지를 3등분하면 4, 3, 3페이지가 된다.
    """
    _require_document(page_count)
    parts = _parse_positive_int(normalize_expression(text), "분할 개수를 입력해 주세요.")
    if parts > page_count:
        raise PageParseError(f"분할 개수는 전체 페이지 수({page_count})보다 클 수 없습니다.")

    base, extra = divmod(page_count, parts)
    groups: list[list[int]] = []
    start = 0
    for index in range(parts):
        size = base + (1 if index < extra else 0)
        groups.append(list(range(start, start + size)))
        start += size
    return groups


def groups_for_mode(mode: SplitMode | str, expression: str, page_count: int) -> list[list[int]]:
    """분할 방식에 맞는 파서를 호출한다.

    페이지 입력은 결과 파일이 하나이므로 묶음도 하나다.
    """
    try:
        resolved = mode if isinstance(mode, SplitMode) else SplitMode(mode)
    except ValueError as exc:
        raise PageParseError("알 수 없는 분할 방식입니다.") from exc

    parsers = {
        SplitMode.PAGES: lambda: [parse_selected_pages(expression, page_count)],
        SplitMode.RANGES: lambda: parse_ranges(expression, page_count),
        SplitMode.CHUNK: lambda: parse_fixed_chunks(expression, page_count),
        SplitMode.SPLIT_AT: lambda: parse_split_after(expression, page_count),
        SplitMode.EQUAL: lambda: parse_equal_parts(expression, page_count),
    }
    return parsers[resolved]()


def format_page_span(indices: list[int] | tuple[int, ...]) -> str:
    """0 기반 인덱스를 ``1-3, 5`` 처럼 1 기반 문자열로 되돌린다.

    연속되지 않은 번호는 입력 순서를 유지한다.
    """
    if not indices:
        return ""
    pages = [index + 1 for index in indices]
    parts: list[str] = []
    start = previous = pages[0]
    for page in pages[1:]:
        if page == previous + 1:
            previous = page
            continue
        parts.append(_span(start, previous))
        start = previous = page
    parts.append(_span(start, previous))
    return ", ".join(parts)


def _span(start: int, end: int) -> str:
    if start == end:
        return str(start)
    return f"{start}-{end}"


def _require_document(page_count: int) -> None:
    if page_count < 1:
        raise PageParseError("페이지가 없는 PDF입니다.")


def _split_csv(text: str, empty_message: str, example: str) -> list[str]:
    if not text:
        raise PageParseError(empty_message)
    tokens = [token.strip() for token in text.split(",")]
    if any(not token for token in tokens):
        raise PageParseError(f"형식이 올바르지 않습니다. 예: {example}")
    return tokens


def _parse_page_number(token: str, page_count: int) -> int:
    if not re.fullmatch(r"\d+", token):
        raise PageParseError(f"페이지 번호 형식이 올바르지 않습니다: {token}")
    number = int(token)
    if number < 1 or number > page_count:
        raise PageParseError(f"{number}페이지는 범위 밖입니다. 1부터 {page_count}까지 입력해 주세요.")
    return number


def _parse_positive_int(text: str, empty_message: str) -> int:
    if not text:
        raise PageParseError(empty_message)
    if not re.fullmatch(r"\d+", text):
        raise PageParseError("1 이상의 정수를 입력해 주세요.")
    number = int(text)
    if number < 1:
        raise PageParseError("1 이상의 정수를 입력해 주세요.")
    return number
