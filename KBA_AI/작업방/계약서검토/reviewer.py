"""계약서 검토 에이전트 (LangGraph).

계약서 문장 하나가 들어오면 아래 그래프를 거쳐 검토 결과가 나온다.

    START -> retrieve -> review --(문제 발견)--> verify -> END
                           |
                           +------(문제 없음)--------------> END

  retrieve : RAG(Chroma)에서 문장과 비슷한 가이드라인/약관 조각을 검색한다.
  review   : LLM 이 참고 문서와 비교해 위배 여부를 판단하고, 문제가 있으면 수정 문구를 만든다.
  verify   : 수정이 정말 필요하고 근거가 있는지 LLM 이 한 번 더 확인한다. (불필요한 수정 방지)

stream_review() 는 계약서 전체를 문장 순서대로 검토하면서 결과를 하나씩 내보낸다.
"""
import difflib
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from typing import TypedDict

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

import config
from rag import search_similar


# ------------------------------------------------------------------ 데이터 구조
class ReviewState(TypedDict, total=False):
    """그래프의 각 단계(노드)가 주고받는 데이터."""

    sentence: str          # 검토 대상 문장
    before: str            # 바로 앞 문장 (문맥 참고용)
    after: str             # 바로 뒤 문장 (문맥 참고용)
    references: list[str]  # RAG 검색 결과
    has_issue: bool        # 위배·보완 필요 여부
    reason: str            # 판단 이유
    revised: str           # 수정 문구


class ReviewResult(BaseModel):
    """review 노드에서 LLM 이 반드시 따라야 하는 출력 형식."""

    has_issue: bool = Field(description="가이드라인/약관에 위배되거나 보완이 필요하면 true")
    reason: str = Field(description="판단 이유를 한 문장으로. 문제가 없으면 빈 문자열")
    revised_text: str = Field(
        description="has_issue 가 true 일 때, 수정한 '대상 문장 전체'. 아니면 빈 문자열"
    )


class VerifyResult(BaseModel):
    """verify 노드에서 LLM 이 반드시 따라야 하는 출력 형식."""

    approved: bool = Field(description="수정이 필요하고 참고 문서에 근거하면 true")


# ------------------------------------------------------------------ 프롬프트
REVIEW_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "당신은 계약서 검토 전문가입니다. [검토 대상 문장]이 [참고 문서]"
            "(가이드라인/약관)에 위배되거나 보완이 필요한지 판단하세요.\n"
            "규칙:\n"
            "1. 참고 문서는 30자 정도로 잘린 조각이라 문맥이 불완전할 수 있습니다. "
            "근거가 분명할 때만 문제가 있다고 판단하세요.\n"
            "2. 참고 문서와 관련이 없거나 근거가 불분명하면 has_issue 는 false 입니다.\n"
            "3. 수정은 최소한으로 하세요. 위배된 부분만 고치고, 조항 번호·말투·어미·띄어쓰기 등 "
            "나머지는 원문 그대로 유지합니다. (예: '~할 수 없다' 가 문제라면 '~할 수 있다' 로만 바꿉니다.)\n"
            "4. [검토 대상 문장]은 PDF 줄바꿈 때문에 문장의 일부만 잘려 나온 조각일 수 있습니다. "
            "대상 문장에 없는 내용을 새로 덧붙이거나 문장을 완성하려고 하지 마세요. "
            "수정은 대상 문장에 실제로 적혀 있는 표현을 바꾸는 것만 허용됩니다. "
            "위배되는 표현이 앞·뒤 문장에 있다면 이 문장은 has_issue 를 false 로 두세요. "
            "(예: 대상 문장이 '...발생한 때에는 갑과 을은' 처럼 서술어 없이 끝나면 문장을 완성하지 말고 "
            "has_issue 를 false 로 둡니다.)\n"
            "5. [앞 문장]과 [뒤 문장]은 문맥 파악용입니다. 이 문장들은 수정하지 마세요.\n"
            "6. has_issue 가 true 이면 revised_text 에 수정한 '검토 대상 문장 전체'를, "
            "reason 에 어떤 참고 문서 내용과 어긋나는지 한 문장을 쓰세요. "
            "false 이면 revised_text 와 reason 은 빈 문자열로 두세요.",
        ),
        (
            "human",
            "[참고 문서]\n{references}\n\n"
            "[앞 문장]\n{before}\n\n"
            "[검토 대상 문장]\n{sentence}\n\n"
            "[뒤 문장]\n{after}",
        ),
    ]
)

VERIFY_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "당신은 계약서 수정안을 감수하는 검토자입니다. 원문과 수정안, 참고 문서를 보고 "
            "수정이 (1) 참고 문서에 근거하고 (2) 꼭 필요하며 (3) 원문의 다른 의미를 "
            "불필요하게 바꾸지 않았고 (4) 원문에 없던 내용을 새로 덧붙이지 않았다면 "
            "approved 를 true 로 하세요. 하나라도 어긋나면 false 입니다. "
            "(원문은 PDF 줄바꿈으로 잘린 문장 조각일 수 있으므로, 문장을 임의로 완성한 수정안은 거절합니다.)",
        ),
        (
            "human",
            "[참고 문서]\n{references}\n\n[원문]\n{sentence}\n\n"
            "[수정안]\n{revised}\n\n[수정 이유]\n{reason}",
        ),
    ]
)


# ------------------------------------------------------------------ LLM
@lru_cache(maxsize=1)
def _llm() -> ChatOpenAI:
    # temperature=0 : 같은 문장에는 되도록 같은 결과가 나오게 한다.
    return ChatOpenAI(model=config.LLM_MODEL, temperature=0)


def _is_faithful_edit(original: str, revised: str) -> bool:
    """수정문이 원문을 크게 벗어나 새 내용을 잔뜩 덧붙이지 않았는지 확인한다.

    원문과 수정문을 글자 단위로 비교해 '새로 들어간 글자 수'를 센다.
    (설정값 MAX_INSERT_RATIO 를 넘으면 원문 조각을 임의로 완성한 것으로 보고 버린다.)
    """
    matcher = difflib.SequenceMatcher(None, original, revised, autojunk=False)
    inserted = sum(
        j2 - j1 for tag, _, _, j1, j2 in matcher.get_opcodes() if tag in ("insert", "replace")
    )
    return inserted <= max(config.MIN_INSERT_ALLOWED, config.MAX_INSERT_RATIO * len(original))


def _format_references(references: list[str]) -> str:
    return "\n".join(references) if references else "(검색된 참고 문서 없음)"


# ------------------------------------------------------------------ 그래프의 노드들
def retrieve_node(state: ReviewState) -> dict:
    """RAG 에서 계약서 문장과 비슷한 가이드라인/약관 조각을 찾는다."""
    references, seen = [], set()
    for doc in search_similar(state["sentence"]):
        text = doc.page_content.strip()
        if text in seen:  # 겹치는 조각이 중복으로 나오는 것을 걸러낸다
            continue
        seen.add(text)
        source = doc.metadata.get("source_file", "알 수 없음")
        page = doc.metadata.get("page")
        where = f"{source} {page + 1}쪽" if isinstance(page, int) else source
        references.append(f"- {text} (출처: {where})")
    return {"references": references}


def review_node(state: ReviewState) -> dict:
    """참고 문서와 비교해 위배 여부를 판단하고 수정 문구를 만든다."""
    chain = REVIEW_PROMPT | _llm().with_structured_output(ReviewResult)
    result: ReviewResult = chain.invoke(
        {
            "references": _format_references(state["references"]),
            "before": state.get("before") or "(없음)",
            "sentence": state["sentence"],
            "after": state.get("after") or "(없음)",
        }
    )
    revised = result.revised_text.strip()
    original = state["sentence"]
    # 수정문이 비었거나 공백만 다른 경우에는 '문제 없음'으로 본다.
    changed = bool(revised) and "".join(revised.split()) != "".join(original.split())
    # LLM 이 잘린 문장 조각을 멋대로 완성해 버리는 경우를 코드로 한 번 더 걸러낸다.
    ok = changed and _is_faithful_edit(original, revised)
    return {
        "has_issue": result.has_issue and ok,
        "reason": result.reason.strip(),
        "revised": revised,
    }


def verify_node(state: ReviewState) -> dict:
    """수정안이 타당한지 한 번 더 확인한다. 타당하지 않으면 '문제 없음'으로 되돌린다."""
    chain = VERIFY_PROMPT | _llm().with_structured_output(VerifyResult)
    result: VerifyResult = chain.invoke(
        {
            "references": _format_references(state["references"]),
            "sentence": state["sentence"],
            "revised": state["revised"],
            "reason": state["reason"],
        }
    )
    if result.approved:
        return {}
    return {"has_issue": False, "reason": "", "revised": ""}


def route_after_review(state: ReviewState) -> str:
    """review 결과에 따라 다음 단계를 고른다."""
    return "verify" if state.get("has_issue") else END


@lru_cache(maxsize=1)
def build_graph():
    """그래프를 한 번만 조립(compile)해서 재사용한다."""
    graph = StateGraph(ReviewState)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("review", review_node)
    graph.add_node("verify", verify_node)

    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "review")
    graph.add_conditional_edges("review", route_after_review, {"verify": "verify", END: END})
    graph.add_edge("verify", END)
    return graph.compile()


# ------------------------------------------------------------------ 계약서 전체 검토
def _review_one(sentences: list[str], i: int) -> dict:
    """i 번째 문장 하나를 검토해서 화면 전송용 dict 로 돌려준다."""
    sentence = sentences[i]
    item = {"original": sentence, "revised": None, "reason": ""}

    # 쪽번호처럼 너무 짧은 조각은 검토할 내용이 없으므로 원문만 출력한다.
    if len(sentence.strip()) < config.MIN_REVIEW_CHARS:
        return item

    before = sentences[i - 1][-config.CONTEXT_CHARS :] if i > 0 else ""
    after = sentences[i + 1][: config.CONTEXT_CHARS] if i + 1 < len(sentences) else ""
    try:
        result = build_graph().invoke({"sentence": sentence, "before": before, "after": after})
    except Exception as exc:  # 한 문장이 실패해도 전체 검토는 계속한다
        item["error"] = f"검토 중 오류가 발생했습니다: {exc}"
        return item

    if result.get("has_issue"):
        item["revised"] = result["revised"]
        item["reason"] = result.get("reason", "")
    return item


def stream_review(sentences: list[str]):
    """계약서를 문장 순서대로 검토하며 결과를 하나씩 내보낸다. (제너레이터)

    여러 문장을 동시에 검토해 속도를 높이되, 결과는 항상 원문 순서대로 내보낸다.
    """
    total = len(sentences)
    yield {"type": "start", "total": total}

    issues = 0
    executor = ThreadPoolExecutor(max_workers=config.REVIEW_WORKERS)
    futures = [executor.submit(_review_one, sentences, i) for i in range(total)]
    try:
        for i, future in enumerate(futures):
            item = future.result()  # i 번째 문장의 검토가 끝날 때까지 기다린다
            if item["revised"]:
                issues += 1
            yield {"type": "sentence", "index": i + 1, "total": total, **item}
    finally:
        # 화면을 닫는 등 중간에 끊기면 아직 시작하지 않은 검토는 취소한다.
        executor.shutdown(wait=False, cancel_futures=True)

    yield {
        "type": "done",
        "text": f"계약서 검토가 완료되었습니다. 총 {total}개 문장 중 {issues}개 문장에 수정 제안이 있습니다.",
    }
