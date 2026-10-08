"""경로, 컬럼 매핑, 임계값, 툴팁 항목. 컬럼명과 임계값은 이 파일에서만 정의한다."""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
PROMPT_PATH = BASE_DIR / "prompts" / "report_system.md"

DATA_FILES = {
    "info": "customer_info.xlsx",
    "meeting": "customer_meeting.xlsx",
    "news": "customer_news.xlsx",
    "sales": "customer_sales.xlsx",
}

SHEETS = {
    "info": "고객사정보",
    "meeting": "고객사별_미팅기록",
    "news": "산업군뉴스_DB_상세",
    "sales": "최근5년_납품이력",
}

# 내부 표준명 -> 실제 Excel 컬럼명
COLUMN_MAP = {
    "info": {
        "customer_name": "고객사명",
        "founded_year": "창립년도",
        "ceo_name": "대표이사명",
        "employee_count": "종업원수",
        "prev_year_revenue": "전년도 매출액",
        "prev_year_profit": "전년도 영업이익",
        "main_products": "주요생산품목",
        "address": "주소",
        "credit_rating": "신용등급",
        "purchased_steel": "당사 구매 철강재명",
        "our_sales": "당사 매출액",
        "latitude": "위도",
        "longitude": "경도",
    },
    "meeting": {
        "meeting_date": "일자",
        "customer_name": "고객사명",
        "manager": "관리직원",
        "contact_name": "고객사담당자명",
        "issue": "고객사 주요이슈",
        "request": "요청사항",
    },
    "news": {
        "news_date": "일자",
        "source": "뉴스 소스",
        "customer_name": "관련 고객사",
        "content": "내용",
        "impact": "고객사에 미치는 영향",
    },
    "sales": {
        "sales_date": "납품일",
        "customer_name": "고객사명",
        "product_name": "제품명",
        "product_code": "제품코드",
        "quantity_ton": "구매량(톤)",
        "amount_thousand_krw": "구매액(천원)",
        "sales_manager": "관리 사원명",
    },
}

JOIN_KEY = "customer_name"

FIELD_LABELS = {
    "customer_name": "거래처명",
    "founded_year": "창립년도",
    "ceo_name": "대표이사명",
    "employee_count": "종업원수",
    "prev_year_revenue": "전년도 매출액",
    "prev_year_profit": "전년도 영업이익",
    "main_products": "주요생산품목",
    "address": "주소",
    "credit_rating": "신용등급",
    "purchased_steel": "당사 구매 철강재명",
    "our_sales": "당사 매출액",
    "latitude": "위도",
    "longitude": "경도",
    "status": "상태",
    "status_reason": "상태 근거",
    "latest_meeting_date": "최근 방문일",
    "latest_sales_amount": "최근 매출",
    "latest_sales_date": "최근 납품일",
    "first_sales_date": "첫 납품일",
    "meeting_date": "일자",
    "manager": "관리직원",
    "contact_name": "고객사담당자명",
    "issue": "고객사 주요이슈",
    "request": "요청사항",
    "news_date": "일자",
    "source": "출처",
    "content": "내용",
    "impact": "고객사에 미치는 영향",
    "sales_date": "납품일",
    "product_name": "제품명",
    "product_code": "제품코드",
    "quantity_ton": "구매량(톤)",
    "amount_thousand_krw": "구매액(천원)",
    "sales_manager": "관리 사원명",
}

# 호버 툴팁에 표시할 내부 표준 컬럼. 산업군 컬럼이 없어 주요생산품목으로 대체.
TOOLTIP_FIELDS = [
    "customer_name",
    "main_products",
    "status",
    "latest_meeting_date",
    "latest_sales_amount",
]

INFO_SUMMARY_FIELDS = [
    "address",
    "credit_rating",
    "ceo_name",
    "founded_year",
    "employee_count",
    "prev_year_revenue",
    "prev_year_profit",
    "main_products",
    "purchased_steel",
    "our_sales",
]

STATUS_ORDER = ["위험", "신규", "일반"]
STATUS_LABELS = {
    "신규": "신규 거래처",
    "일반": "일반",
    "위험": "위험",
}

# 미정 값은 None. 비어 있으면 해당 조건은 상태 판정에서 제외된다.
# 거래 시작일은 customer_info에 없으므로 첫 납품일(first_sales_date)을 사용한다.
NEW_CUSTOMER_DAYS = None  # 예: 365

# 임시 시연: 신규 기간 데이터가 없어 노란 핀을 확인할 거래처. 비우면 적용하지 않는다.
DEMO_NEW_CUSTOMERS = ["세림건설기술", "미래플랜트건설"]

# 예: {"recent_months": 3, "previous_months": 3, "decline_rate": 0.3}
SALES_DECLINE_RULE = None

# 예: {"window_days": 365, "min_count": 3}
REPEAT_REQUEST_RULE = None

# None이면 실행일. 매출 데이터가 실행일보다 오래되었으면 날짜를 지정하는 것을 권장.
REFERENCE_DATE = None

LAT_MIN, LAT_MAX = -90.0, 90.0
LON_MIN, LON_MAX = -180.0, 180.0

MEETING_LIST_LIMIT = 12
SALES_TREND_MONTHS = 24
NEWS_PREVIEW_CHARS = 80
