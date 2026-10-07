"""일반 질문 처리: RAG 를 거치지 않고 LLM 에 바로 물어본다."""
from functools import lru_cache

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

import config

SYSTEM_PROMPT = (
    "당신은 친절한 AI 어시스턴트입니다. 계약서와 법률 관련 질문에는 일반적인 정보를 "
    "쉽게 설명하되, 법률 자문을 대체하지 않는다는 점을 필요할 때 짧게 안내하세요. "
    "한국어로 답변합니다."
)


@lru_cache(maxsize=1)
def _llm() -> ChatOpenAI:
    return ChatOpenAI(model=config.LLM_MODEL, temperature=0.3)


def stream_answer(message: str, history: list[dict]):
    """질문에 대한 답변을 토큰 단위로 내보낸다. (제너레이터)

    history : [{"role": "user" | "assistant", "content": "..."}, ...]  (이전 대화)
    """
    messages = [SystemMessage(content=SYSTEM_PROMPT)]
    for turn in history[-config.CHAT_HISTORY_LIMIT :]:
        cls = HumanMessage if turn.get("role") == "user" else AIMessage
        messages.append(cls(content=str(turn.get("content", ""))))
    messages.append(HumanMessage(content=message))

    for chunk in _llm().stream(messages):
        if chunk.content:
            yield {"type": "token", "text": chunk.content}
    yield {"type": "done"}
