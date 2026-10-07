"""RAG 구축: 가이드라인/약관 PDF -> 분할 -> 임베딩 -> Chroma DB 저장.

흐름
  1) PyPDFLoader      : PDF를 쪽(page) 단위 Document 로 읽는다.
  2) 텍스트 분할      : RecursiveCharacterTextSplitter (30글자, 겹침 5글자)
  3) 임베딩 + 저장    : text-embedding-3-small 로 벡터화해서 Chroma 에 저장한다.

각 단계는 tqdm 진행률 이벤트를 yield 하므로, 웹 화면에 진행 상황이 실시간으로 보인다.
"""
from collections import Counter
from functools import lru_cache

from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

import config
from pdf_utils import count_pages
from progress import WebProgress


@lru_cache(maxsize=1)
def get_vectorstore() -> Chroma:
    """Chroma 벡터 DB 객체를 한 번만 만들어서 재사용한다.

    persist_directory 를 지정했으므로 서버를 껐다 켜도 저장된 RAG 문서가 유지된다.
    """
    config.CHROMA_DIR.mkdir(exist_ok=True)
    embeddings = OpenAIEmbeddings(model=config.EMBEDDING_MODEL)
    return Chroma(
        collection_name=config.COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=str(config.CHROMA_DIR),
    )


def list_sources() -> dict:
    """DB에 저장된 RAG 파일 목록과 조각(chunk) 수를 돌려준다. (화면 상태 표시용)"""
    metadatas = get_vectorstore().get(include=["metadatas"])["metadatas"] or []
    counts = Counter(m.get("source_file", "알 수 없음") for m in metadatas)
    return {
        "files": [{"name": name, "chunks": n} for name, n in counts.items()],
        "total_chunks": sum(counts.values()),
    }


def ingest_pdfs(files: list[tuple[str, str]]):
    """RAG용 PDF 여러 개를 처리한다. (제너레이터: 진행 이벤트를 하나씩 내보낸다)

    files : [(저장된 임시 경로, 사용자가 올린 원래 파일명), ...]
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.RAG_CHUNK_SIZE,
        chunk_overlap=config.RAG_CHUNK_OVERLAP,
        separators=config.SEPARATORS,
    )

    # ---- 1단계: PDF 읽기 (쪽 단위로 진행률 표시)
    total_pages = sum(count_pages(path) for path, _ in files)
    yield {"type": "info", "text": f"PDF {len(files)}개, 총 {total_pages}쪽을 읽습니다."}

    bar = WebProgress("load", "1/3  PDF 읽는 중", total_pages, unit="쪽")
    pages = []  # (원래 파일명, 쪽 Document)
    for path, name in files:
        for doc in PyPDFLoader(path).lazy_load():
            pages.append((name, doc))
            yield bar.update()
    bar.close()

    # ---- 2단계: 텍스트 분할 (쪽 단위로 진행률 표시)
    bar = WebProgress("split", "2/3  문서 분할 중", len(pages), unit="쪽")
    chunks = []
    for name, page in pages:
        if page.page_content.strip():
            for chunk in splitter.split_documents([page]):
                if not chunk.page_content.strip():
                    continue  # 빈 조각은 임베딩 API 오류의 원인이라 제외
                # PyPDFLoader 가 넣는 source 는 임시 경로이므로, 원래 파일명을 따로 보관한다.
                chunk.metadata["source_file"] = name
                chunks.append(chunk)
        yield bar.update()
    bar.close()

    if not chunks:
        raise ValueError(
            "PDF에서 텍스트를 찾지 못했습니다. 스캔본(이미지) PDF는 지원하지 않습니다."
        )

    # ---- 3단계: 임베딩 + Chroma 저장 (조각 묶음 단위로 진행률 표시)
    store = get_vectorstore()

    # 같은 이름의 파일을 다시 올리면 이전에 저장된 내용을 지우고 새로 넣는다. (중복 방지)
    for name in {name for _, name in files}:
        store.delete(where={"source_file": name})

    bar = WebProgress("embed", "3/3  임베딩 · 저장 중", len(chunks), unit="조각")
    batch_size = config.EMBED_BATCH_SIZE
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        store.add_documents(batch)
        yield bar.update(len(batch))
    bar.close()

    summary = list_sources()
    yield {
        "type": "done",
        "text": (
            f"RAG 파일 업로드가 완료되었습니다. 이번에 {len(chunks)}개 조각을 저장했고, "
            f"DB에는 총 {summary['total_chunks']}개 조각이 있습니다."
        ),
        "rag": summary,
    }


def search_similar(query: str, k: int | None = None):
    """계약서 문장과 비슷한 RAG 조각을 검색한다. (Document 목록 반환)"""
    return get_vectorstore().similarity_search(query, k=k or config.RETRIEVE_K)
