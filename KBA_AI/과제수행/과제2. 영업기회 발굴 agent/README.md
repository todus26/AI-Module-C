# 영업기회 발굴 Agent

영업 담당자가 지도에서 거래처를 선택해 현황, 매출, 방문일지, 뉴스를 보고 방문 준비 보고서 초안을 작성하는 Streamlit 앱입니다.

## 실행 방법

```bash
python -m pip install -r requirements.txt
copy .env.example .env
```

`.env`에 LLM API 키를 넣습니다. 키가 없어도 앱은 실행되며, 보고서는 자료 정리 초안으로 만들어집니다.

```
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini
LLM_BASE_URL=https://api.openai.com/v1
```

```bash
streamlit run app.py
```

데이터 파일은 `data/`의 `customer_info.xlsx`, `customer_meeting.xlsx`, `customer_news.xlsx`, `customer_sales.xlsx`를 사용합니다.

## 상태 판정 기준

`config.py`의 값이 비어 있으면 해당 조건은 판정에서 빠집니다. 지금은 세 값 모두 비어 있어 거래처는 일반으로 표시됩니다.

```python
NEW_CUSTOMER_DAYS = 365
SALES_DECLINE_RULE = {"recent_months": 3, "previous_months": 3, "decline_rate": 0.3}
REPEAT_REQUEST_RULE = {"window_days": 365, "min_count": 3}
REFERENCE_DATE = None  # None이면 실행일
```

매출 파일이 실행일보다 오래되었으면 `REFERENCE_DATE`를 최신 납품일에 맞추는 것을 권장합니다.

## 점검 스크립트

```bash
python scripts/inspect_data.py
python scripts/verify_pipeline.py
```
