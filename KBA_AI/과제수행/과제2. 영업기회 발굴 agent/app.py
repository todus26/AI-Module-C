"""영업기회 발굴 Agent 진입점."""

from __future__ import annotations

import logging
from datetime import datetime

import pandas as pd
import streamlit as st

import config
from src import theme
from src.calendar_panel import render_calendar
from src.chatbot import render_chatbot
from src.data_loader import DataLoadError, file_mtimes, load_all
from src.detail_panel import render_detail, render_empty
from src.map_view import focus_customer, render_map
from src.status import apply_status, reference_date, status_counts
from src.unlocated import render_map_search, render_status_chips, render_unlocated

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="영업기회 발굴 Agent",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_data(show_spinner=False)
def load_cached(mtime_key: tuple):
    bundle = load_all()
    customers = apply_status(bundle.customers, bundle.sales, bundle.meeting)
    return customers, bundle.meeting, bundle.sales, bundle.news, bundle.file_mtimes


def _data_as_of(meeting: pd.DataFrame, sales: pd.DataFrame, news: pd.DataFrame, mtimes: dict) -> str:
    dates = []
    for frame, col in ((meeting, "meeting_date"), (sales, "sales_date"), (news, "news_date")):
        if not frame.empty:
            latest = pd.to_datetime(frame[col], errors="coerce").max()
            if pd.notna(latest):
                dates.append(latest)
    if dates:
        return max(dates).strftime("%Y-%m-%d")
    if mtimes:
        latest_file = max(mtimes.values())
        if isinstance(latest_file, datetime):
            return latest_file.strftime("%Y-%m-%d")
    return reference_date().isoformat()


def _select(name: str, customers: pd.DataFrame) -> None:
    previous = st.session_state.get("selected_customer")
    st.session_state["selected_customer"] = name
    if previous != name:
        st.session_state["report_text"] = ""
        st.session_state["report_error"] = ""
        st.session_state["report_customer"] = None
    focus_customer(customers, name)


def _selected_row(customers: pd.DataFrame) -> pd.Series | None:
    name = st.session_state.get("selected_customer")
    if not name:
        return None
    rows = customers[customers["customer_name"] == name]
    if rows.empty:
        return None
    return rows.iloc[0]


def main() -> None:
    st.markdown(f"<style>{theme.inject_css()}</style>", unsafe_allow_html=True)

    try:
        mtimes = file_mtimes()
        mtime_key = tuple(mtimes[k] for k in sorted(mtimes)) + tuple(
            config.DEMO_NEW_CUSTOMERS or []
        )
        with st.spinner("데이터를 불러오는 중입니다"):
            customers, meeting, sales, news, file_times = load_cached(mtime_key)
    except DataLoadError as exc:
        st.error(str(exc))
        return
    except Exception as exc:
        logger.exception("데이터 로드 실패")
        st.error(f"데이터를 불러오지 못했습니다. 파일명과 컬럼을 확인하세요. ({exc})")
        return

    as_of = _data_as_of(meeting, sales, news, file_times)
    title_col, meta_col = st.columns([3, 1])
    title_col.markdown(
        '<div class="header-title">영업기회 발굴 Agent</div>',
        unsafe_allow_html=True,
    )
    meta_col.markdown(
        f'<div class="header-meta">데이터 기준일 {as_of}</div>',
        unsafe_allow_html=True,
    )

    counts = status_counts(customers)
    with st.sidebar:
        picked_meeting = render_calendar(customers, meeting)
        if picked_meeting:
            _select(picked_meeting, customers)
            st.rerun()
        st.divider()
        render_chatbot(_selected_row(customers), meeting, sales)

    map_col, detail_col = st.columns([1.35, 1], gap="medium")
    with map_col:
        st.caption("거래처 검색")
        searched = render_map_search(customers, key_prefix="map_search")
        if searched:
            _select(searched, customers)
            st.rerun()
        st.caption("상태")
        selected_statuses = render_status_chips(counts)
        filtered = customers[customers["status"].isin(selected_statuses)].copy()
        picked_unlocated = render_unlocated(filtered)
        if picked_unlocated:
            _select(picked_unlocated, customers)
            st.rerun()

        if filtered.empty:
            st.warning("조건에 맞는 거래처가 없습니다")
        else:
            selected_name = st.session_state.get("selected_customer")
            clicked = render_map(filtered, selected_name)
            names = set(customers["customer_name"].astype(str))
            click_token = clicked if clicked in names else ""
            if click_token and click_token != st.session_state.get("selected_customer"):
                st.session_state["last_map_click"] = click_token
                _select(click_token, customers)
                st.rerun()

    with detail_col:
        selected_name = st.session_state.get("selected_customer")
        if not selected_name:
            render_empty()
            return
        rows = customers[customers["customer_name"] == selected_name]
        if rows.empty:
            render_empty()
            return
        render_detail(rows.iloc[0], meeting, sales, news)


if __name__ == "__main__":
    main()
