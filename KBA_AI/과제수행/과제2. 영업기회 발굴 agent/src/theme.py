"""색상과 화면 스타일. 색상 값은 이 모듈에서만 정의한다."""

# 시프티블루 (Shiftee 브랜드 컬러). 출처: shiftee.io 디자인 시스템.
PRIMARY = "#004DC1"
PRIMARY_DARK = "#0A2864"
PRIMARY_PRESSED = "#0062CC"
PRIMARY_LIGHT = "#E8F1FC"
BACKGROUND = "#FFFFFF"
BACKGROUND_MUTED = "#F4F6F8"
BORDER = "#D9DEE7"
TEXT = "#343A40"
TEXT_MUTED = "#5C6370"

STATUS_COLORS = {
    "신규": "#C9A227",
    "일반": "#3D8B5F",
    "위험": "#C04545",
}

STATUS_TEXT_COLORS = {
    "신규": "#5C4A00",
    "일반": "#FFFFFF",
    "위험": "#FFFFFF",
}


def inject_css() -> str:
    new = STATUS_COLORS["신규"]
    normal = STATUS_COLORS["일반"]
    risk = STATUS_COLORS["위험"]
    return f"""
@import url("https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css");

html, body, .stApp, .stMarkdown, p, h1, h2, h3, h4, label, .stCaption {{
  font-family: Pretendard, "Malgun Gothic", "Apple SD Gothic Neo", sans-serif;
  color: {TEXT};
}}
.stApp {{
  background: {BACKGROUND_MUTED};
}}
.block-container {{
  padding-top: 1.2rem;
  padding-bottom: 2rem;
}}
hr {{
  margin: 0.6rem 0 1rem 0;
  border: none;
  border-top: 1px solid {BORDER};
}}
.header-title {{
  font-size: 1.35rem;
  font-weight: 700;
  color: {PRIMARY_DARK};
  padding-bottom: 0.4rem;
  border-bottom: 1px solid {BORDER};
}}
.header-meta {{
  font-size: 0.85rem;
  color: {TEXT_MUTED};
  text-align: right;
  padding-top: 0.45rem;
}}
iframe[title="streamlit_folium.st_folium"] {{
  width: 100%;
  min-height: 540px;
}}
[data-testid="stIconMaterial"],
span[translate="no"] {{
  font-family: "Material Symbols Rounded", "Material Icons", sans-serif !important;
}}
.badge {{
  display: inline-block;
  padding: 0.15rem 0.55rem;
  border-radius: 2px;
  font-size: 0.78rem;
  font-weight: 600;
  line-height: 1.4;
}}
.badge-신규 {{ background: {new}; color: {STATUS_TEXT_COLORS["신규"]}; }}
.badge-일반 {{ background: {normal}; color: {STATUS_TEXT_COLORS["일반"]}; }}
.badge-위험 {{ background: {risk}; color: {STATUS_TEXT_COLORS["위험"]}; }}
.panel-card {{
  background: {BACKGROUND};
  border: 1px solid {BORDER};
  padding: 0.9rem 1rem;
}}
.muted {{
  color: {TEXT_MUTED};
  font-size: 0.9rem;
}}
.kv {{
  font-size: 0.92rem;
}}
.kv dt {{
  color: {TEXT_MUTED};
  font-size: 0.8rem;
  margin-top: 0.45rem;
}}
.kv dd {{
  margin: 0;
  word-break: keep-all;
  overflow-wrap: anywhere;
}}
.news-item {{
  border-top: 1px solid {BORDER};
  padding: 0.7rem 0;
}}
.unlocated-item {{
  display: flex;
  justify-content: space-between;
  gap: 0.5rem;
  padding: 0.25rem 0;
  font-size: 0.9rem;
}}
.map-toolbar {{
  background: {BACKGROUND};
  border: 1px solid {BORDER};
  padding: 0.7rem 0.85rem 0.4rem 0.85rem;
  margin-bottom: 0.6rem;
}}
.status-underline {{
  height: 4px;
  margin: -0.4rem 0 0.5rem 0;
}}
div[data-testid="stSidebar"] {{
  background: {BACKGROUND};
}}
div[data-testid="stSidebar"] .stButton button {{
  text-align: left;
  justify-content: flex-start;
  white-space: normal;
  height: auto;
  padding-top: 0.35rem;
  padding-bottom: 0.35rem;
}}
.cal-title {{
  font-weight: 700;
  color: {PRIMARY_DARK};
  font-size: 1rem;
  padding-top: 0.35rem;
}}
.cal-month {{
  text-align: center;
  font-weight: 600;
  color: {PRIMARY_DARK};
  padding-top: 0.4rem;
  font-size: 0.92rem;
  letter-spacing: 0.02em;
}}
.cal-rule {{
  border-top: 1px solid {BORDER};
  margin: 0.15rem 0 0.55rem 0;
}}
.cal-wd {{
  text-align: center;
  font-size: 0.78rem;
  color: {TEXT_MUTED};
  padding-bottom: 0.2rem;
}}
.cal-empty {{
  min-height: 30px;
}}
.cal-selected {{
  color: {TEXT_MUTED};
  font-size: 0.88rem;
  margin: 0.2rem 0 0.1rem 0;
}}
section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"]:has([data-testid="stColumn"]:nth-child(4)):not(:has([data-testid="stColumn"]:nth-child(5))) button {{
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  color: {PRIMARY_DARK} !important;
  min-height: 28px !important;
  height: 28px !important;
  padding: 0 !important;
}}
section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"]:has([data-testid="stColumn"]:nth-child(7)) {{
  gap: 0 !important;
  margin-bottom: -0.55rem !important;
}}
section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"]:has([data-testid="stColumn"]:nth-child(7)) [data-testid="stColumn"] {{
  display: flex !important;
  justify-content: center !important;
}}
section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"]:has([data-testid="stColumn"]:nth-child(7)) button,
section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"]:has([data-testid="stColumn"]:nth-child(7)) button * {{
  font-size: 13px !important;
  line-height: 1 !important;
  justify-content: center !important;
  align-items: center !important;
  text-align: center !important;
  font-weight: 400 !important;
  background: transparent !important;
  box-shadow: none !important;
  color: {TEXT} !important;
}}
section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"]:has([data-testid="stColumn"]:nth-child(2)):not(:has([data-testid="stColumn"]:nth-child(3))) button {{
  white-space: nowrap !important;
  justify-content: center !important;
  text-align: center !important;
  min-height: 2.1rem !important;
  height: auto !important;
}}
section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"]:has([data-testid="stColumn"]:nth-child(7)) button {{
  width: 32px !important;
  height: 32px !important;
  min-width: 32px !important;
  min-height: 32px !important;
  max-width: 32px !important;
  max-height: 32px !important;
  padding: 0 !important;
  margin: 0 auto 12px auto !important;
  border: none !important;
  border-radius: 50% !important;
  overflow: visible !important;
  position: relative !important;
  flex-direction: column !important;
}}
section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"]:has([data-testid="stColumn"]:nth-child(7)) button,
section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"]:has([data-testid="stColumn"]:nth-child(7)) button * {{
  overflow: visible !important;
}}
section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"]:has([data-testid="stColumn"]:nth-child(7)) button p {{
  margin: 0 !important;
}}
section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"]:has([data-testid="stColumn"]:nth-child(7)) button p:nth-of-type(2) {{
  position: absolute !important;
  left: 0 !important;
  right: 0 !important;
  bottom: -8px !important;
  font-size: 10px !important;
  line-height: 1 !important;
  color: {PRIMARY_DARK} !important;
}}
section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"]:has([data-testid="stColumn"]:nth-child(7)) button[data-testid="stBaseButton-primary"] {{
  background: transparent !important;
  border: 1.5px solid {PRIMARY_DARK} !important;
  color: {PRIMARY_DARK} !important;
}}
section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"]:has([data-testid="stColumn"]:nth-child(7)) button[data-testid="stBaseButton-primary"] * {{
  color: {PRIMARY_DARK} !important;
}}
"""
