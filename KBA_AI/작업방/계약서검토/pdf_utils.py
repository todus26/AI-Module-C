"""PDF 관련 작은 도우미 함수."""
from pypdf import PdfReader


def count_pages(path: str) -> int:
    """PDF의 쪽수를 센다. (진행률 막대의 전체 크기를 정하는 데 사용)"""
    return len(PdfReader(path).pages)
