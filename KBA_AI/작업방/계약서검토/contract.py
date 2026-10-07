"""계약서 업로드 처리: PDF -> 문장(조각) 분할.

분할된 문장 목록은 서버 메모리(STATE)에 보관하고,
화면에서 '계약서 검토' 버튼을 누르면 reviewer.py 가 이 목록을 한 문장씩 검토한다.
"""
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

import config
from pdf_utils import count_pages
from progress import WebProgress

# 현재 업로드된 계약서 (혼자 쓰는 로컬 웹이라 전역 변수 하나로 충분하다)
STATE = {"filename": None, "pages": 0, "sentences": []}


def get_state() -> dict:
    """화면 표시용 요약 정보."""
    return {
        "filename": STATE["filename"],
        "pages": STATE["pages"],
        "sentence_count": len(STATE["sentences"]),
    }


def ingest_contract(path: str, name: str):
    """계약서 PDF 한 개를 읽고 분할한다. (제너레이터: 진행 이벤트를 하나씩 내보낸다)"""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.CONTRACT_CHUNK_SIZE,
        chunk_overlap=config.CONTRACT_CHUNK_OVERLAP,  # 계약서는 겹치지 않게 0
        separators=config.SEPARATORS,
    )

    total_pages = count_pages(path)
    yield {"type": "info", "text": f"'{name}' ({total_pages}쪽)을 읽습니다."}

    # ---- 1단계: PDF 읽기
    bar = WebProgress("load", "1/2  계약서 읽는 중", total_pages, unit="쪽")
    pages = []
    for doc in PyPDFLoader(path).lazy_load():
        pages.append(doc)
        yield bar.update()
    bar.close()

    # ---- 2단계: 문장 분할
    bar = WebProgress("split", "2/2  문장 분할 중", len(pages), unit="쪽")
    sentences = []
    for page in pages:
        if page.page_content.strip():
            for chunk in splitter.split_documents([page]):
                text = chunk.page_content.strip()
                if text:
                    sentences.append(text)
        yield bar.update()
    bar.close()

    if not sentences:
        raise ValueError(
            "계약서에서 텍스트를 찾지 못했습니다. 스캔본(이미지) PDF는 지원하지 않습니다."
        )

    STATE.update(filename=name, pages=len(pages), sentences=sentences)
    yield {
        "type": "done",
        "text": (
            f"계약서 업로드가 완료되었습니다. 총 {len(pages)}쪽, "
            f"{len(sentences)}개 문장으로 나누었습니다. "
            "왼쪽의 '계약서 검토' 버튼을 눌러 검토를 시작하세요."
        ),
        "contract": get_state(),
    }
