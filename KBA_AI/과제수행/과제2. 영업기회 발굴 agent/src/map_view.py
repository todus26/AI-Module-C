"""위치가 있는 거래처를 folium 지도에 표시한다."""

from __future__ import annotations

import html
import re

import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

import config
from src import theme


def _tooltip_html(row: pd.Series) -> str:
    lines: list[str] = []
    for field in config.TOOLTIP_FIELDS:
        label = config.FIELD_LABELS.get(field, field)
        value = row.get(field)
        if field == "latest_sales_amount":
            text = format_amount(value)
        elif field in {"latest_meeting_date", "latest_sales_date", "first_sales_date"}:
            text = format_date(value)
        else:
            text = "" if pd.isna(value) else str(value)
        if not text:
            text = "-"
        lines.append(
            f"<b>{html.escape(label)}</b>: {html.escape(text)}"
        )
    return "<br>".join(lines)


def format_date(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return ""
    return parsed.strftime("%Y-%m-%d")


def format_amount(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number >= 100000:
        return f"{number / 100000:.1f}억원"
    return f"{number:,.0f}천원"


def render_map(customers: pd.DataFrame, selected_customer: str | None) -> str | None:
    located = customers[customers["has_location"]]
    if located.empty:
        st.info("위치가 확인된 거래처가 없습니다. 위치 미확인 목록에서 선택하세요.")
        return None

    fit_now = False
    if "map_center" not in st.session_state:
        st.session_state.map_center = [
            float(located["latitude"].astype(float).mean()),
            float(located["longitude"].astype(float).mean()),
        ]
        st.session_state.map_zoom = 7
        fit_now = True

    fmap = folium.Map(
        location=st.session_state.map_center,
        zoom_start=int(st.session_state.map_zoom),
        tiles="OpenStreetMap",
    )
    if fit_now:
        fmap.fit_bounds(
            [
                [float(located["latitude"].min()), float(located["longitude"].min())],
                [float(located["latitude"].max()), float(located["longitude"].max())],
            ]
        )

    counts = {
        status: int((located["status"] == status).sum()) for status in config.STATUS_ORDER
    }
    for _, row in located.iterrows():
        name = str(row["customer_name"])
        selected = selected_customer == name
        status = str(row.get("status") or "일반")
        color = theme.STATUS_COLORS.get(status, theme.STATUS_COLORS["일반"])
        radius = 12 if selected else (10 if status == "신규" else 8)
        folium.CircleMarker(
            location=[float(row["latitude"]), float(row["longitude"])],
            radius=radius,
            color=theme.PRIMARY_DARK if selected else "#FFFFFF",
            weight=3 if selected else 1,
            fill=True,
            fill_color=color,
            fill_opacity=0.92,
            tooltip=folium.Tooltip(_tooltip_html(row), sticky=False),
            popup=folium.Popup(name, parse_html=False, max_width=200),
        ).add_to(fmap)

    folium_kwargs = {
        "height": 540,
        "width": None,
        "use_container_width": True,
        "returned_objects": ["last_object_clicked", "last_object_clicked_popup", "center", "zoom"],
        "key": "customer_map",
    }
    if not fit_now:
        folium_kwargs["center"] = st.session_state.map_center
        folium_kwargs["zoom"] = int(st.session_state.map_zoom)
    output = st_folium(fmap, **folium_kwargs)
    _render_legend(counts)
    if output:
        center = output.get("center")
        zoom = output.get("zoom")
        if center and "lat" in center and "lng" in center:
            new_center = [center["lat"], center["lng"]]
            old = st.session_state.map_center
            if abs(new_center[0] - old[0]) > 1e-6 or abs(new_center[1] - old[1]) > 1e-6:
                st.session_state.map_center = new_center
        if zoom and int(zoom) != int(st.session_state.map_zoom):
            st.session_state.map_zoom = int(zoom)

        popup = output.get("last_object_clicked_popup")
        if popup:
            cleaned = re.sub(r"<[^>]+>", "", str(popup)).strip()
            return cleaned or None
        clicked = output.get("last_object_clicked")
        if clicked and "lat" in clicked and "lng" in clicked:
            return _match_customer(located, clicked["lat"], clicked["lng"])
    return None


def _match_customer(located: pd.DataFrame, lat: float, lon: float) -> str | None:
    if located.empty:
        return None
    dist = (located["latitude"].astype(float) - lat) ** 2 + (located["longitude"].astype(float) - lon) ** 2
    idx = dist.idxmin()
    if dist.loc[idx] > 0.0004:
        return None
    return str(located.loc[idx, "customer_name"])


def _render_legend(counts: dict[str, int]) -> None:
    parts = []
    for status in config.STATUS_ORDER:
        color = theme.STATUS_COLORS[status]
        label = config.STATUS_LABELS[status]
        n = counts.get(status, 0)
        parts.append(
            f'<span style="display:inline-flex;align-items:center;margin-right:12px;">'
            f'<span style="width:10px;height:10px;background:{color};display:inline-block;'
            f'margin-right:6px;border:1px solid {theme.BORDER};"></span>'
            f"{html.escape(label)} {n}</span>"
        )
    st.markdown("".join(parts), unsafe_allow_html=True)


def focus_customer(customers: pd.DataFrame, name: str) -> None:
    row = customers[customers["customer_name"] == name]
    if row.empty or not bool(row.iloc[0]["has_location"]):
        return
    st.session_state.map_center = [float(row.iloc[0]["latitude"]), float(row.iloc[0]["longitude"])]
    st.session_state.map_zoom = 11
