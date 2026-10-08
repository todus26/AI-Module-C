"""사이드바 챗봇. 보고서와 같은 LLM 키를 사용한다."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src import llm
from src.map_view import format_amount, format_date

EXAMPLE_QUESTIONS = [
    "지금 선택된 거래처까지 교통수단이 어떻게 돼?",
    "이 거래처의 최근 요청사항을 정리해 줘.",
    "최근 매출과 주요 구매 품목은 어떻게 돼?",
    "방문할 때 확인하면 좋은 점은 뭐야?",
]


def _customer_context(row: pd.Series | None, meeting: pd.DataFrame, sales: pd.DataFrame) -> str:
    if row is None:
        return "현재 선택된 거래처가 없습니다. 지도에서 거래처를 고른 뒤 질문하세요."
    name = str(row["customer_name"])
    meet_lines = []
    subset = meeting[meeting["join_key"] == row["join_key"]].sort_values("meeting_date", ascending=False).head(5)
    for _, item in subset.iterrows():
        meet_lines.append(
            f"- {format_date(item.get('meeting_date'))}: {item.get('issue') or '-'} / {item.get('request') or '-'}"
        )
    sales_lines = []
    sold = sales[sales["join_key"] == row["join_key"]].sort_values("sales_date", ascending=False).head(5)
    for _, item in sold.iterrows():
        sales_lines.append(
            f"- {format_date(item.get('sales_date'))} {item.get('product_name')} "
            f"{item.get('quantity_ton')}톤 / {format_amount(item.get('amount_thousand_krw'))}"
        )
    return (
        f"선택된 거래처: {name}\n"
        f"주소: {row.get('address') or '자료 없음'}\n"
        f"위도: {row.get('latitude')} 경도: {row.get('longitude')}\n"
        f"상태: {row.get('status')} ({row.get('status_reason')})\n"
        f"주요생산품목: {row.get('main_products')}\n"
        f"당사 구매 철강재: {row.get('purchased_steel')}\n"
        f"최근 방문일: {format_date(row.get('latest_meeting_date')) or '자료 없음'}\n"
        f"최근 매출: {format_amount(row.get('latest_sales_amount')) or '자료 없음'}\n"
        "최근 방문\n" + ("\n".join(meet_lines) or "자료 없음") + "\n"
        "최근 납품\n" + ("\n".join(sales_lines) or "자료 없음")
    )


SYSTEM_PROMPT = """당신은 영업 담당자의 방문 준비를 돕는 비서다.
아래 거래처 자료를 우선 근거로 짧게 답한다.
자료에 없는 사실은 단정하지 않는다.
교통수단 질문은 주소와 위경도를 바탕으로 일반적인 방문 경로(기차, 버스, 차량 등)를 안내하되,
실시간 배차와 정확한 소요시간은 추정임을 한 줄로 밝힌다.
출발지는 밝히지 않았으면 서울 강남 또는 수도권 영업거점을 가정했다고 명시한다.
이모지는 쓰지 않는다.
"""


def _ask(question: str, row: pd.Series | None, meeting: pd.DataFrame, sales: pd.DataFrame) -> None:
    st.session_state.chat_messages.append({"role": "user", "content": question})
    context = _customer_context(row, meeting, sales)
    history = st.session_state.chat_messages[-8:]
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": "거래처 자료\n" + context},
    ]
    messages.extend(history)
    try:
        answer = llm.complete(messages, temperature=0.3)
    except Exception as exc:
        answer = f"답변을 만들지 못했습니다. {exc}"
    st.session_state.chat_messages.append({"role": "assistant", "content": answer})


def render_chatbot(row: pd.Series | None, meeting: pd.DataFrame, sales: pd.DataFrame) -> None:
    st.markdown("**질문**")
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []

    selected = str(row["customer_name"]) if row is not None else None
    if selected:
        st.caption(f"기준 거래처: {selected}")
    else:
        st.caption("거래처를 선택하면 주소와 현황을 기준으로 답합니다.")

    st.caption("예시 질문")
    for i, question in enumerate(EXAMPLE_QUESTIONS):
        if st.button(question, key=f"chat_ex_{i}", width="stretch"):
            _ask(question, row, meeting, sales)
            st.rerun()

    with st.container(height=240):
        if not st.session_state.chat_messages:
            st.caption("질문을 고르거나 아래에 직접 입력하세요.")
        for msg in st.session_state.chat_messages:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

    prompt = st.chat_input("거래처에 대해 물어보세요")
    if prompt:
        _ask(prompt, row, meeting, sales)
        st.rerun()
