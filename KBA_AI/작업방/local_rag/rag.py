import hashlib
import math
import re
import threading
import warnings
from collections import defaultdict
from typing import Iterator

warnings.filterwarnings("ignore", message=".*langchain-community.*")

from langchain_chroma import Chroma
from langchain_community.chat_models import ChatLlamaCpp
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.embeddings import LlamaCppEmbeddings
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_text_splitters import RecursiveCharacterTextSplitter
from llama_cpp import Llama

import config


ANSWER_SYSTEM_PROMPT = (
    "당신은 사용자가 업로드한 PDF 문서를 근거로 질문에 답하는 한국어 문서 질의응답 어시스턴트입니다. "
    "항상 사용자가 함께 제공하는 [참고 문서]의 내용만 사용해 답하고, 문서에 없는 내용은 절대 지어내지 않습니다."
)

# 2.4B 소형 모델은 시스템 메시지보다 마지막 사용자 메시지의 지시를 훨씬 잘 따르므로
# 참고 문서와 규칙을 질문과 함께 마지막 턴에 넣는다.
ANSWER_USER_PROMPT = """[참고 문서]
{context}

[질문]
{question}

[답변 규칙]
- 위 [참고 문서]에 적힌 내용만 근거로 핵심을 간결하게 답하세요.
- 질문과 관련된 조건이나 경우가 여러 개라면 빠짐없이 모두 정리해 답하세요.
- 일반 상식, 추측, 조언을 덧붙이지 마세요.
- 질문에 '그것', '이것'처럼 앞의 대화를 가리키는 말이 있으면 이전 대화를 참고해 대상을 파악하세요.
- [참고 문서]에서 질문의 답을 찾을 수 없으면 다른 말 없이 "{no_info}"라고만 답하세요."""

SUMMARY_SYSTEM_PROMPT = """주어진 문서 조각의 핵심 내용을 한국어 한두 문장(100자 이내)으로 요약하세요.
문서에 없는 내용은 덧붙이지 말고, 요약문만 출력하세요."""


def _normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


class NormalizedLlamaCppEmbeddings(LlamaCppEmbeddings):
    """bge-m3 는 L2 정규화된 벡터로 코사인 유사도를 계산하도록 학습되었다."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [_normalize(v) for v in super().embed_documents(texts)]

    def embed_query(self, text: str) -> list[float]:
        return _normalize(super().embed_query(text))


def _extractive_preview(text: str, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    m = list(re.finditer(r"[.?!。]\s", cut))
    if m and m[-1].end() > limit * 0.5:
        return cut[: m[-1].end()].strip()
    return cut.rstrip() + "…"


def _is_no_info(answer: str) -> bool:
    compact = re.sub(r"\s+", "", answer)
    return not compact or re.sub(r"\s+", "", config.NO_INFO_MESSAGE) in compact


class RAGEngine:
    def __init__(self) -> None:
        self._llm_lock = threading.Lock()
        self._emb_lock = threading.Lock()
        self._histories: dict[str, InMemoryChatMessageHistory] = defaultdict(
            InMemoryChatMessageHistory
        )
        self._display_logs: dict[str, list[dict]] = defaultdict(list)
        self._summary_cache: dict[str, str] = {}

        embedding_client = Llama(
            model_path=config.EMBEDDING_MODEL_PATH,
            embedding=True,
            n_ctx=config.EMBEDDING_N_CTX,
            n_batch=config.EMBEDDING_N_CTX,
            n_ubatch=config.EMBEDDING_N_CTX,
            n_threads=config.N_THREADS,
            n_gpu_layers=config.N_GPU_LAYERS,
            verbose=False,
        )
        self.embeddings = NormalizedLlamaCppEmbeddings(client=embedding_client)

        self.llm = ChatLlamaCpp(
            model_path=config.LLM_MODEL_PATH,
            n_ctx=config.LLM_N_CTX,
            n_threads=config.N_THREADS,
            n_gpu_layers=config.N_GPU_LAYERS,
            max_tokens=config.LLM_MAX_TOKENS,
            temperature=config.LLM_TEMPERATURE,
            repeat_penalty=1.1,
            verbose=False,
        )

        self.vectorstore = Chroma(
            collection_name=config.COLLECTION_NAME,
            embedding_function=self.embeddings,
            persist_directory=config.CHROMA_DIR,
            collection_metadata={"hnsw:space": "cosine"},
        )

        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.CHUNK_SIZE,
            chunk_overlap=config.CHUNK_OVERLAP,
            separators=config.SEPARATORS,
            keep_separator="end",
        )

        self.answer_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", ANSWER_SYSTEM_PROMPT),
                MessagesPlaceholder("history"),
                ("human", ANSWER_USER_PROMPT),
            ]
        )
        self.summary_chain = (
            ChatPromptTemplate.from_messages(
                [("system", SUMMARY_SYSTEM_PROMPT), ("human", "{text}")]
            )
            | self.llm.bind(max_tokens=120, temperature=0.0)
            | StrOutputParser()
        )

    # ── 문서 관리 ────────────────────────────────────────────
    @staticmethod
    def file_hash(path: str) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for block in iter(lambda: f.read(1 << 20), b""):
                h.update(block)
        return h.hexdigest()[:16]

    def has_document(self, doc_id: str) -> bool:
        return bool(self.vectorstore.get(where={"doc_id": doc_id}, limit=1)["ids"])

    def ingest_pdf(self, path: str, filename: str, doc_id: str) -> dict:
        pages = PyPDFLoader(path).load()
        page_docs = [
            Document(
                page_content=p.page_content,
                metadata={
                    "source": filename,
                    "doc_id": doc_id,
                    "page": int(p.metadata.get("page", 0)) + 1,
                    "page_label": str(p.metadata.get("page_label", "")),
                },
            )
            for p in pages
            if p.page_content.strip()
        ]
        chunks = self.splitter.split_documents(page_docs)
        if not chunks:
            raise ValueError("PDF에서 텍스트를 추출할 수 없습니다. (스캔 이미지 PDF일 수 있습니다)")

        for i, c in enumerate(chunks):
            c.metadata["chunk_index"] = i
        ids = [f"{doc_id}-{i}" for i in range(len(chunks))]
        with self._emb_lock:
            self.vectorstore.add_documents(chunks, ids=ids)
        return {"pages": len(pages), "chunks": len(chunks)}

    def list_documents(self) -> list[dict]:
        metas = self.vectorstore.get(include=["metadatas"])["metadatas"]
        docs: dict[str, dict] = {}
        for m in metas:
            d = docs.setdefault(
                m["doc_id"], {"doc_id": m["doc_id"], "name": m["source"], "chunks": 0, "pages": set()}
            )
            d["chunks"] += 1
            d["pages"].add(m["page"])
        return sorted(
            ({**d, "pages": len(d["pages"])} for d in docs.values()),
            key=lambda d: d["name"],
        )

    def delete_document(self, doc_id: str) -> int:
        ids = self.vectorstore.get(where={"doc_id": doc_id})["ids"]
        if ids:
            self.vectorstore.delete(ids=ids)
        return len(ids)

    # ── 대화 메모리 ──────────────────────────────────────────
    def _recent_history(self, session_id: str) -> list:
        messages = self._histories[session_id].messages[-config.MEMORY_MAX_TURNS * 2 :]
        trimmed = []
        for m in messages:
            if isinstance(m, AIMessage) and len(m.content) > config.MEMORY_MAX_ANSWER_CHARS:
                m = AIMessage(content=m.content[: config.MEMORY_MAX_ANSWER_CHARS] + "…")
            trimmed.append(m)
        return trimmed

    def get_display_log(self, session_id: str) -> list[dict]:
        return self._display_logs[session_id]

    def clear_session(self, session_id: str) -> None:
        self._histories.pop(session_id, None)
        self._display_logs.pop(session_id, None)

    def _remember(self, session_id: str, question: str, answer: str, sources: list[dict]) -> None:
        self._histories[session_id].add_messages(
            [HumanMessage(content=question), AIMessage(content=answer)]
        )
        self._display_logs[session_id].append(
            {"question": question, "answer": answer, "sources": sources}
        )

    # ── 검색 & 답변 ──────────────────────────────────────────
    def retrieve(self, question: str, history: list | None = None) -> list[tuple[Document, float]]:
        """질문 단독 검색과 '최근 질문들 + 현재 질문' 검색 결과를 합쳐 상위 TOP_K 를 고른다.

        "그건 언제까지 신청해?" 같은 후속 질문은 이전 질문과 합쳐야 올바른 chunk 가 잡히고,
        주제가 바뀐 질문은 단독 검색 점수가 더 높아 자연스럽게 우선된다.
        """
        if not self.vectorstore.get(limit=1)["ids"]:
            return []
        prev_questions = [m.content for m in (history or []) if isinstance(m, HumanMessage)]
        prev_questions = prev_questions[-config.HISTORY_QUERY_TURNS :]

        best: dict[str, tuple[Document, float]] = {}

        def collect(query: str) -> float:
            hits = self.vectorstore.similarity_search_with_relevance_scores(query, k=config.TOP_K)
            for doc, score in hits:
                key = f"{doc.metadata['doc_id']}-{doc.metadata['chunk_index']}"
                if key not in best or score > best[key][1]:
                    best[key] = (doc, score)
            return max((s for _, s in hits), default=0.0)

        with self._emb_lock:
            question_score = collect(question)
            if prev_questions:
                collect("\n".join([*prev_questions, question]))

        results = sorted(best.values(), key=lambda x: x[1], reverse=True)[: config.TOP_K]
        if (
            not results
            or results[0][1] < config.RELEVANCE_THRESHOLD
            or question_score < config.MIN_QUESTION_RELEVANCE
        ):
            return []
        return results

    @staticmethod
    def _format_context(results: list[tuple[Document, float]]) -> str:
        return "\n\n".join(
            f"[문서 {i}] ({doc.metadata['source']}, {doc.metadata['page']}페이지)\n{doc.page_content}"
            for i, (doc, _) in enumerate(results, 1)
        )

    @staticmethod
    def _source_payload(results: list[tuple[Document, float]]) -> list[dict]:
        return [
            {
                "id": f"{doc.metadata['doc_id']}-{doc.metadata['chunk_index']}",
                "source": doc.metadata["source"],
                "page": doc.metadata["page"],
                "score": round(float(score), 3),
                "preview": _extractive_preview(doc.page_content),
                "content": doc.page_content,
            }
            for doc, score in results
        ]

    def stream_answer(self, session_id: str, question: str) -> Iterator[dict]:
        history = self._recent_history(session_id)

        yield {"type": "status", "message": "관련 문서를 검색하는 중…"}
        results = self.retrieve(question, history)

        if not results:
            self._remember(session_id, question, config.NO_INFO_MESSAGE, [])
            yield {"type": "token", "text": config.NO_INFO_MESSAGE}
            yield {"type": "done", "answer": config.NO_INFO_MESSAGE, "sources": [], "no_info": True}
            return

        yield {"type": "status", "message": "답변을 생성하는 중…"}
        messages = self.answer_prompt.format_messages(
            no_info=config.NO_INFO_MESSAGE,
            context=self._format_context(results),
            history=history,
            question=question,
        )

        parts: list[str] = []
        with self._llm_lock:
            for chunk in self.llm.stream(messages):
                if chunk.content:
                    parts.append(chunk.content)
                    yield {"type": "token", "text": chunk.content}
        answer = "".join(parts).strip()

        if _is_no_info(answer):
            self._remember(session_id, question, config.NO_INFO_MESSAGE, [])
            yield {"type": "done", "answer": config.NO_INFO_MESSAGE, "sources": [], "no_info": True}
            return

        sources = self._source_payload(results)
        self._remember(session_id, question, answer, sources)
        yield {"type": "done", "answer": answer, "sources": sources, "no_info": False}

    def summarize_chunk(self, chunk_id: str) -> str:
        if chunk_id in self._summary_cache:
            return self._summary_cache[chunk_id]
        found = self.vectorstore.get(ids=[chunk_id])
        if not found["documents"]:
            raise KeyError(chunk_id)
        text = found["documents"][0]
        with self._llm_lock:
            summary = self.summary_chain.invoke({"text": text}).strip()
        summary = summary or _extractive_preview(text)
        self._summary_cache[chunk_id] = summary
        for log in self._display_logs.values():
            for turn in log:
                for s in turn["sources"]:
                    if s["id"] == chunk_id:
                        s["summary"] = summary
        return summary
