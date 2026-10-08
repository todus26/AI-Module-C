"""검색, 상태 필터, 위치 미확인 목록."""

from __future__ import annotations

import pandas as pd
import streamlit as st

import config
from src import theme
from src.map_view import format_date


def render_unlocated(customers: pd.DataFrame) -> str | None:
    missing = customers[~customers["has_location"]].copy()
    if missing.empty:
        return None
    missing = missing.sort_values(["status", "customer_name"])
    selected = None
    with st.expander(f"위치 미확인 ({len(missing)})", expanded=False):
        for _, row in missing.iterrows():
            name = str(row["customer_name"])
            status = str(row.get("status") or "일반")
            visited = format_date(row.get("latest_meeting_date")) or "-"
            cols = st.columns([3, 1])
            cols[0].markdown(f"{name}  \n<span class='muted'>{status} · 최근 방문 {visited}</span>", unsafe_allow_html=True)
            if cols[1].button("선택", key=f"unlocated_{name}"):
                selected = name
    return selected


def render_map_search(customers: pd.DataFrame, key_prefix: str = "search") -> str | None:
    query = st.text_input(
        "거래처명 검색",
        placeholder="거래처명 일부",
        key=f"{key_prefix}_query",
        label_visibility="collapsed",
    )
    if not query:
        return None
    key = query.strip()
    matches = customers[customers["customer_name"].astype(str).str.contains(key, case=False, na=False)]
    if matches.empty:
        st.caption("검색 결과가 없습니다.")
        return None
    selected = None
    names = matches["customer_name"].tolist()
    cols = st.columns(min(4, len(names)))
    for i, name in enumerate(names):
        if cols[i % len(cols)].button(name, key=f"{key_prefix}_btn_{name}"):
            selected = name
    return selected


def render_status_chips(counts: dict[str, int] | None = None) -> list[str]:
    counts = counts or {}
    selected: list[str] = []
    cols = st.columns(len(config.STATUS_ORDER), gap="small")
    for i, status in enumerate(config.STATUS_ORDER):
        color = theme.STATUS_COLORS[status]
        n = int(counts.get(status, 0))
        with cols[i]:
            checked = st.checkbox(
                f"{status} {n}",
                value=True,
                key=f"status_chk_{status}",
            )
            st.markdown(
                f'<div class="status-underline" style="background:{color};"></div>',
                unsafe_allow_html=True,
            )
            if checked:
                selected.append(status)
    return selected
