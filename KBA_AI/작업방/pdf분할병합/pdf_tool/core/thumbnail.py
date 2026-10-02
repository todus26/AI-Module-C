"""PDF 페이지를 PNG 바이트로 렌더링한다.

pypdf는 페이지를 그리지 못하므로 썸네일에만 PyMuPDF를 쓴다.
"""

from threading import Lock

import fitz

THUMBNAIL_WIDTH = 160
_CACHE: dict[tuple[str, int, int], bytes] = {}
_CACHE_LOCK = Lock()
_CACHE_LIMIT = 400


class ThumbnailError(Exception):
    """썸네일을 만들지 못했을 때 발생한다."""


def render_pages(path: str, indices: list[int], max_width: int = THUMBNAIL_WIDTH) -> list[bytes | None]:
    """한 파일을 한 번만 열어 요청한 페이지의 PNG를 만든다.

    Args:
        path: PDF 경로.
        indices: 0 기반 페이지 번호.
        max_width: 가로 픽셀. 세로는 비율을 유지한다.

    Returns:
        입력과 같은 순서의 PNG 바이트. 해당 페이지만 실패하면 None.

    Raises:
        ThumbnailError: 파일 자체를 열 수 없을 때.
    """
    results: list[bytes | None] = [None] * len(indices)
    pending: list[int] = []
    with _CACHE_LOCK:
        for position, index in enumerate(indices):
            cached = _CACHE.get((path, index, max_width))
            if cached is None:
                pending.append(position)
            else:
                results[position] = cached
    if not pending:
        return results

    try:
        document = fitz.open(path)
    except Exception as exc:
        raise ThumbnailError("손상되었거나 열 수 없는 PDF입니다.") from exc

    try:
        if document.needs_pass:
            raise ThumbnailError("암호화된 PDF입니다. 암호를 해제한 뒤 다시 선택해 주세요.")
        if document.page_count < 1:
            raise ThumbnailError("페이지가 없는 PDF입니다.")

        for position in pending:
            index = indices[position]
            if index < 0 or index >= document.page_count:
                continue
            try:
                page = document[index]
                width = page.rect.width or 1
                scale = max_width / width
                pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
                data = pixmap.tobytes("png")
            except Exception:
                results[position] = None
                continue
            results[position] = data
            _store_cache(path, index, max_width, data)
    finally:
        document.close()
    return results


def _store_cache(path: str, index: int, max_width: int, data: bytes) -> None:
    with _CACHE_LOCK:
        _CACHE[(path, index, max_width)] = data
        if len(_CACHE) > _CACHE_LIMIT:
            _CACHE.pop(next(iter(_CACHE)))
