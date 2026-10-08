"""선택한 거래처의 요약, 뉴스, 보고서 탭."""

from __future__ import annotations

import html

import pandas as pd
import streamlit as st

import config
from src import theme
from src.map_view import format_amount, format_date
from src.export_report import to_docx_bytes, to_pdf_bytes
from src.report import generate_report


def _badge(status: str) -> str:
    label = html.escape(status)
    return f'<span class="badge badge-{label}">{label}</span>'


def _customer_news(news: pd.DataFrame, join_key: str) -> pd.DataFrame:
    subset = news[news["join_key"] == join_key].copy()
    if subset.empty:
        return subset
    return subset.sort_values("news_date", ascending=False)


def _customer_meetings(meeting: pd.DataFrame, join_key: str) -> pd.DataFrame:
    subset = meeting[meeting["join_key"] == join_key].copy()
    if subset.empty:
        return subset
    return subset.sort_values("meeting_date", ascending=False)


def _customer_sales(sales: pd.DataFrame, join_key: str) -> pd.DataFrame:
    subset = sales[sales["join_key"] == join_key].copy()
    if subset.empty:
        return subset
    return subset.sort_values("sales_date", ascending=False)


def render_empty() -> None:
    st.info("지도에서 거래처를 선택하세요")


def render_detail(
    row: pd.Series,
    meeting: pd.DataFrame,
    sales: pd.DataFrame,
    news: pd.DataFrame,
) -> None:
    name = str(row["customer_name"])
    status = str(row.get("status") or "일반")
    st.markdown(
        f"<div style='display:flex;gap:8px;align-items:center;margin-bottom:8px;'>"
        f"<span style='font-size:1.15rem;font-weight:700;color:{theme.PRIMARY_DARK};'>"
        f"{html.escape(name)}</span>{_badge(status)}</div>",
        unsafe_allow_html=True,
    )

    tab_summary, tab_news, tab_report = st.tabs(["요약", "뉴스", "보고서"])
    with tab_summary:
        _render_summary(row, meeting, sales)
    with tab_news:
        _render_news(row, news)
        if st.button(
            "보고서 작성",
            key=f"btn_report_from_news_{name}",
            on_click=_run_report,
            args=(row, meeting, sales, news),
        ):
            st.rerun()
    with tab_report:
        _render_report(row, meeting, sales, news)


def _render_summary(row: pd.Series, meeting: pd.DataFrame, sales: pd.DataFrame) -> None:
    st.markdown("**기본 정보**")
    lines = []
    for field in config.INFO_SUMMARY_FIELDS:
        label = config.FIELD_LABELS.get(field, field)
        value = row.get(field)
        text = "-" if value is None or (isinstance(value, float) and pd.isna(value)) else str(value)
        lines.append(f"{label}: {text}")
    st.text("\n".join(lines))

    st.markdown("**매출**")
    sales_rows = _customer_sales(sales, row["join_key"])
    latest_amt = format_amount(row.get("latest_sales_amount")) or "자료 없음"
    latest_date = format_date(row.get("latest_sales_date")) or "-"
    st.caption(f"최근 매출 {latest_amt} ({latest_date})")
    if sales_rows.empty:
        st.write("매출 이력이 없습니다.")
    else:
        top_products = (
            sales_rows.groupby("product_name", as_index=False)["amount_thousand_krw"]
            .sum()
            .sort_values("amount_thousand_krw", ascending=False)
            .head(5)
        )
        st.write("주요 구매 품목")
        st.dataframe(
            top_products.rename(
                columns={
                    "product_name": "제품명",
                    "amount_thousand_krw": "구매액(천원)",
                }
            ),
            hide_index=True,
            width="stretch",
        )
        monthly = sales_rows.copy()
        monthly["월"] = pd.to_datetime(monthly["sales_date"]).dt.to_period("M").dt.to_timestamp()
        trend = monthly.groupby("월", as_index=False)["amount_thousand_krw"].sum().sort_values("월")
        if not trend.empty:
            st.write("매출 추이 (월별 구매액, 천원)")
            st.line_chart(trend, x="월", y="amount_thousand_krw", height=180)

    st.markdown("**방문 이력**")
    meetings = _customer_meetings(meeting, row["join_key"]).head(config.MEETING_LIST_LIMIT)
    if meetings.empty:
        st.write("방문 이력이 없습니다.")
    else:
        show = meetings[["meeting_date", "contact_name", "issue", "request"]].copy()
        show["meeting_date"] = show["meeting_date"].map(format_date)
        st.dataframe(
            show.rename(
                columns={
                    "meeting_date": "일자",
                    "contact_name": "담당자",
                    "issue": "주요이슈",
                    "request": "요청사항",
                }
            ),
            hide_index=True,
            width="stretch",
        )

    st.markdown("**상태 근거**")
    st.write(row.get("status_reason") or "-")


def _news_key(customer_name: str, index: object) -> str:
    return f"news_sel_{customer_name}_{index}"


def _render_news(row: pd.Series, news: pd.DataFrame) -> None:
    name = str(row["customer_name"])
    rows = _customer_news(news, row["join_key"])
    if rows.empty:
        st.write("관련 뉴스가 없습니다")
        return

    st.caption("보고서에 포함할 뉴스를 선택하세요. 기본값은 전체 선택입니다.")
    for idx, item in rows.iterrows():
        date_text = format_date(item.get("news_date")) or "-"
        source = item.get("source") or "-"
        content = str(item.get("content") or "")
        impact = str(item.get("impact") or "")
        preview = content if len(content) <= config.NEWS_PREVIEW_CHARS else content[: config.NEWS_PREVIEW_CHARS] + "..."
        label = f"[{date_text} | {source}] {preview}"
        st.checkbox(label, value=True, key=_news_key(name, idx))
        with st.expander("본문 및 영향", expanded=False):
            st.write(content)
            if impact:
                st.caption("고객사에 미치는 영향")
                st.write(impact)


def _selected_news_for(row: pd.Series, news: pd.DataFrame) -> pd.DataFrame:
    name = str(row["customer_name"])
    rows = _customer_news(news, row["join_key"])
    if rows.empty:
        return rows
    picked = []
    for idx, item in rows.iterrows():
        key = _news_key(name, idx)
        if st.session_state.get(key, True):
            picked.append(item)
    if not picked:
        return rows.iloc[0:0]
    return pd.DataFrame(picked)


def _run_report(row: pd.Series, meeting: pd.DataFrame, sales: pd.DataFrame, news: pd.DataFrame) -> None:
    name = str(row["customer_name"])
    st.session_state["report_customer"] = name
    st.session_state["report_error"] = ""
    st.session_state["report_nonce"] = int(st.session_state.get("report_nonce") or 0) + 1
    with st.spinner("보고서를 작성하고 있습니다"):
        try:
            selected = _selected_news_for(row, news)
            text, used_llm = generate_report(row, meeting, sales, selected)
            st.session_state["report_text"] = text
            st.session_state["report_used_llm"] = used_llm
        except Exception as exc:
            st.session_state["report_error"] = str(exc)
            if not st.session_state.get("report_text"):
                st.session_state["report_text"] = ""


def _render_report(row: pd.Series, meeting: pd.DataFrame, sales: pd.DataFrame, news: pd.DataFrame) -> None:
    name = str(row["customer_name"])
    if st.session_state.get("report_customer") not in {None, name}:
        st.session_state["report_text"] = ""
        st.session_state["report_error"] = ""
        st.session_state["report_customer"] = None

    if st.button(
        "보고서 작성",
        key=f"btn_report_{name}",
        on_click=_run_report,
        args=(row, meeting, sales, news),
    ):
        st.rerun()

    error = st.session_state.get("report_error") or ""
    text = st.session_state.get("report_text") or ""
    if error:
        st.error(error)
        if st.button("다시 시도", key=f"btn_retry_{name}"):
            _run_report(row, meeting, sales, news)
            st.rerun()
        if text:
            st.caption("이전에 편집 중이던 내용입니다.")
    if not text:
        st.caption("뉴스 탭에서 항목을 고른 뒤 보고서 작성을 누르면 초안이 표시됩니다.")
        return

    st.info("자동 생성된 초안입니다. 내용을 확인하고 수정하세요.")
    if st.session_state.get("report_used_llm") is False:
        st.caption("LLM API 키가 없어 자료 정리 초안을 표시했습니다. .env에 키를 넣으면 모델이 초안을 작성합니다.")
    nonce = int(st.session_state.get("report_nonce") or 0)
    area_key = f"report_area_{name}_{nonce}"
    if area_key not in st.session_state:
        st.session_state[area_key] = text
    edited = st.text_area(
        "보고서",
        height=420,
        key=area_key,
        label_visibility="collapsed",
    )
    if edited:
        st.session_state["report_text"] = edited
    stem = f"{name}_방문준비보고서"
    st.caption("다운로드")
    st.download_button(
        "Markdown (.md)",
        data=edited.encode("utf-8"),
        file_name=f"{stem}.md",
        mime="text/markdown",
        key=f"dl_md_{name}",
        width="stretch",
    )
    try:
        pdf_bytes = to_pdf_bytes(edited)
        st.download_button(
            "PDF (.pdf)",
            data=pdf_bytes,
            file_name=f"{stem}.pdf",
            mime="application/pdf",
            key=f"dl_pdf_{name}",
            width="stretch",
        )
    except Exception as exc:
        st.caption(f"PDF 변환 실패: {exc}")
    try:
        docx_bytes = to_docx_bytes(edited)
        st.download_button(
            "Word (.docx)",
            data=docx_bytes,
            file_name=f"{stem}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            key=f"dl_docx_{name}",
            width="stretch",
        )
    except Exception as exc:
        st.caption(f"Word 변환 실패: {exc}")
