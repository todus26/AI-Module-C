"""사이드바 미팅 일정. 추가분은 세션에만 두고 DB는 쓰지 않는다."""

from __future__ import annotations

import calendar as calmod
from datetime import date, time
from uuid import uuid4

import pandas as pd
import streamlit as st

from src.map_view import format_date

WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]


def _ensure_state() -> None:
    today = date.today()
    if "planned_meetings" not in st.session_state:
        st.session_state.planned_meetings = []
    if "calendar_day" not in st.session_state:
        st.session_state.calendar_day = today
    if "calendar_cursor" not in st.session_state:
        st.session_state.calendar_cursor = today.replace(day=1)


def _shift_month(cursor: date, delta: int) -> date:
    month = cursor.month - 1 + delta
    year = cursor.year + month // 12
    month = month % 12 + 1
    return date(year, month, 1)


def _file_meetings_on(meeting: pd.DataFrame, day: date) -> pd.DataFrame:
    if meeting.empty:
        return meeting.iloc[0:0]
    dates = pd.to_datetime(meeting["meeting_date"], errors="coerce").dt.date
    return meeting[dates == day].copy()


def _planned_on(day: date) -> list[dict]:
    return [item for item in st.session_state.planned_meetings if item.get("date") == day.isoformat()]


def _event_dates(meeting: pd.DataFrame, year: int, month: int) -> set[date]:
    days: set[date] = set()
    for item in st.session_state.planned_meetings:
        try:
            day = date.fromisoformat(item["date"])
        except (TypeError, ValueError):
            continue
        if day.year == year and day.month == month:
            days.add(day)
    if meeting.empty:
        return days
    parsed = pd.to_datetime(meeting["meeting_date"], errors="coerce").dt.date
    for day in parsed.dropna():
        if day.year == year and day.month == month:
            days.add(day)
    return days


def _upcoming(meeting: pd.DataFrame, today: date, limit: int = 6) -> list[dict]:
    rows: list[dict] = []
    for item in st.session_state.planned_meetings:
        day = date.fromisoformat(item["date"])
        if day >= today:
            rows.append(
                {
                    "date": day,
                    "time": item.get("time") or "",
                    "customer_name": item["customer_name"],
                    "memo": item.get("memo") or "",
                    "source": "등록",
                    "id": item["id"],
                }
            )
    if not meeting.empty:
        parsed = meeting.copy()
        parsed["_d"] = pd.to_datetime(parsed["meeting_date"], errors="coerce").dt.date
        future = parsed[parsed["_d"].notna() & (parsed["_d"] >= today)].sort_values("meeting_date")
        for _, row in future.head(limit).iterrows():
            rows.append(
                {
                    "date": row["_d"],
                    "time": "",
                    "customer_name": str(row["customer_name"]),
                    "memo": str(row.get("issue") or row.get("request") or ""),
                    "source": "방문일지",
                    "id": None,
                }
            )
    rows.sort(key=lambda x: (x["date"], x["time"] or "99:99"))
    return rows[:limit]


def _render_month_grid(meeting: pd.DataFrame) -> None:
    cursor = st.session_state.calendar_cursor
    selected = st.session_state.calendar_day
    events = _event_dates(meeting, cursor.year, cursor.month)

    title_col, prev_col, month_col, next_col = st.columns([2.2, 0.5, 1.2, 0.5], gap="small")
    title_col.markdown('<div class="cal-title">방문 일정</div>', unsafe_allow_html=True)
    if prev_col.button("◀", key="cal_prev", type="tertiary", width="stretch"):
        st.session_state.calendar_cursor = _shift_month(cursor, -1)
        st.rerun()
    month_col.markdown(
        f'<div class="cal-month">{cursor.year}.{cursor.month:02d}</div>',
        unsafe_allow_html=True,
    )
    if next_col.button("▶", key="cal_next", type="tertiary", width="stretch"):
        st.session_state.calendar_cursor = _shift_month(cursor, 1)
        st.rerun()
    st.markdown('<div class="cal-rule"></div>', unsafe_allow_html=True)

    labels = st.columns(7, gap="small")
    for i, name in enumerate(WEEKDAYS):
        labels[i].markdown(f'<div class="cal-wd">{name}</div>', unsafe_allow_html=True)

    first_weekday, days_in_month = calmod.monthrange(cursor.year, cursor.month)
    cells: list[int | None] = [None] * first_weekday + list(range(1, days_in_month + 1))
    while len(cells) % 7:
        cells.append(None)

    for row_start in range(0, len(cells), 7):
        cols = st.columns(7, gap="small")
        for i, day_n in enumerate(cells[row_start : row_start + 7]):
            if day_n is None:
                cols[i].markdown('<div class="cal-empty"></div>', unsafe_allow_html=True)
                continue
            day = date(cursor.year, cursor.month, day_n)
            label = f"{day_n}\n\n•" if day in events else str(day_n)
            clicked = cols[i].button(
                label,
                key=f"cal_d_{day.isoformat()}",
                width="stretch",
                type="primary" if day == selected else "tertiary",
            )
            if clicked and day != selected:
                st.session_state.calendar_day = day
                st.rerun()


def render_calendar(customers: pd.DataFrame, meeting: pd.DataFrame) -> str | None:
    _ensure_state()
    picked = None

    _render_month_grid(meeting)
    day = st.session_state.calendar_day
    st.markdown(f'<div class="cal-selected">{day.isoformat()}</div>', unsafe_allow_html=True)

    file_rows = _file_meetings_on(meeting, day)
    planned = _planned_on(day)
    if file_rows.empty and not planned:
        st.caption("예정된 방문이 없습니다")
    else:
        for _, row in file_rows.iterrows():
            name = str(row["customer_name"])
            issue = str(row.get("issue") or "")
            cols = st.columns([3.2, 1.3])
            cols[0].markdown(
                f"{name}  \n<span class='muted'>방문일지 · {issue}</span>",
                unsafe_allow_html=True,
            )
            if cols[1].button("보기", key=f"cal_file_{name}_{format_date(row.get('meeting_date'))}"):
                picked = name
        for item in planned:
            cols = st.columns([3.2, 1.3])
            time_text = f"{item.get('time')} " if item.get("time") else ""
            cols[0].markdown(
                f"{item['customer_name']}  \n<span class='muted'>{time_text}{item.get('memo') or '메모 없음'}</span>",
                unsafe_allow_html=True,
            )
            if cols[1].button("삭제", key=f"cal_del_{item['id']}"):
                st.session_state.planned_meetings = [
                    x for x in st.session_state.planned_meetings if x["id"] != item["id"]
                ]
                st.rerun()

    names = customers["customer_name"].astype(str).tolist()
    default_name = st.session_state.get("selected_customer")
    default_index = names.index(default_name) if default_name in names else 0
    with st.expander("일정 추가", expanded=False):
        customer = st.selectbox("거래처", names, index=default_index, key="cal_add_customer")
        add_day = st.date_input("방문일", value=day, key="cal_add_day")
        add_time = st.time_input("시각", value=time(14, 0), key="cal_add_time")
        memo = st.text_input("메모", placeholder="논의 주제, 장소 등", key="cal_add_memo")
        if st.button("추가", key="cal_add_btn", width="stretch"):
            st.session_state.planned_meetings.append(
                {
                    "id": str(uuid4()),
                    "date": add_day.isoformat(),
                    "time": add_time.strftime("%H:%M"),
                    "customer_name": customer,
                    "memo": memo.strip(),
                }
            )
            st.session_state.calendar_day = add_day
            st.session_state.calendar_cursor = add_day.replace(day=1)
            st.rerun()

    st.caption("다가오는 일정")
    upcoming = _upcoming(meeting, date.today())
    if not upcoming:
        st.caption("예정된 일정이 없습니다.")
        return picked
    for item in upcoming:
        label = f"{item['date'].isoformat()} {item['customer_name']}"
        if st.button(
            label,
            key=f"cal_up_{item['source']}_{item['date']}_{item['customer_name']}_{item.get('id')}",
            width="stretch",
        ):
            picked = item["customer_name"]
            st.session_state.calendar_day = item["date"]
            st.session_state.calendar_cursor = item["date"].replace(day=1)
    return picked
