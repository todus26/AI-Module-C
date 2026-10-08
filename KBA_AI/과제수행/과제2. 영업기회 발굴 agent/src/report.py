"""방문 준비 보고서 초안 생성."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

import config
from src import llm
from src.map_view import format_amount, format_date
from src.status import reference_date


def _read_system_prompt() -> str:
    path: Path = config.PROMPT_PATH
    if not path.exists():
        raise FileNotFoundError(f"보고서 지시문이 없습니다: {path}")
    return path.read_text(encoding="utf-8")


def _meetings_block(meeting: pd.DataFrame, join_key: str) -> str:
    rows = meeting[meeting["join_key"] == join_key].sort_values("meeting_date", ascending=False)
    if rows.empty:
        return "자료 없음"
    lines = []
    for _, item in rows.head(config.MEETING_LIST_LIMIT).iterrows():
        lines.append(
            f"- {format_date(item.get('meeting_date'))} / 담당자 {item.get('contact_name') or '-'} "
            f"/ 이슈: {item.get('issue') or '-'} / 요청: {item.get('request') or '-'}"
        )
    return "\n".join(lines)


def _sales_block(sales: pd.DataFrame, join_key: str) -> str:
    rows = sales[sales["join_key"] == join_key].sort_values("sales_date", ascending=False)
    if rows.empty:
        return "자료 없음"
    top = (
        rows.groupby("product_name", as_index=False)["amount_thousand_krw"]
        .sum()
        .sort_values("amount_thousand_krw", ascending=False)
        .head(8)
    )
    product_lines = [
        f"- {r.product_name}: {format_amount(r.amount_thousand_krw)}" for r in top.itertuples()
    ]
    recent = []
    for _, item in rows.head(8).iterrows():
        recent.append(
            f"- {format_date(item.get('sales_date'))} {item.get('product_name')} "
            f"{item.get('quantity_ton')}톤 / {format_amount(item.get('amount_thousand_krw'))}"
        )
    return "주요 구매 품목\n" + "\n".join(product_lines) + "\n최근 납품\n" + "\n".join(recent)


def _news_block(news: pd.DataFrame) -> str:
    if news is None or news.empty:
        return "자료 없음"
    lines = []
    ordered = news.sort_values("news_date", ascending=False)
    for _, item in ordered.iterrows():
        lines.append(
            f"- {format_date(item.get('news_date'))} / {item.get('source') or '-'}\n"
            f"  내용: {item.get('content') or '-'}\n"
            f"  영향: {item.get('impact') or '-'}"
        )
    return "\n".join(lines)


def build_user_prompt(
    row: pd.Series,
    meeting: pd.DataFrame,
    sales: pd.DataFrame,
    news: pd.DataFrame,
) -> str:
    name = str(row["customer_name"])
    info_lines = [
        f"- 거래처명: {name}",
        f"- 주소: {row.get('address') or '자료 없음'}",
        f"- 대표이사: {row.get('ceo_name') or '자료 없음'}",
        f"- 창립년도: {row.get('founded_year') or '자료 없음'}",
        f"- 종업원수: {row.get('employee_count') or '자료 없음'}",
        f"- 전년도 매출액: {row.get('prev_year_revenue') or '자료 없음'}",
        f"- 전년도 영업이익: {row.get('prev_year_profit') or '자료 없음'}",
        f"- 주요생산품목: {row.get('main_products') or '자료 없음'}",
        f"- 신용등급: {row.get('credit_rating') or '자료 없음'}",
        f"- 당사 구매 철강재: {row.get('purchased_steel') or '자료 없음'}",
        f"- 당사 매출액: {row.get('our_sales') or '자료 없음'}",
        f"- 상태: {row.get('status') or '-'}",
        f"- 상태 근거: {row.get('status_reason') or '-'}",
        f"- 첫 납품일: {format_date(row.get('first_sales_date')) or '자료 없음'}",
        f"- 최근 납품일: {format_date(row.get('latest_sales_date')) or '자료 없음'}",
        f"- 최근 매출: {format_amount(row.get('latest_sales_amount')) or '자료 없음'}",
        f"- 최근 방문일: {format_date(row.get('latest_meeting_date')) or '자료 없음'}",
    ]
    return (
        f"기준일: {reference_date().isoformat()}\n"
        f"거래처명: {name}\n\n"
        "기본정보\n" + "\n".join(info_lines) + "\n\n"
        "매출과 주요 구매 품목\n" + _sales_block(sales, row["join_key"]) + "\n\n"
        "방문일지\n" + _meetings_block(meeting, row["join_key"]) + "\n\n"
        "선택된 뉴스\n" + _news_block(news) + "\n"
    )


def call_llm(system_prompt: str, user_prompt: str) -> str:
    return llm.complete(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    )


def fallback_report(row: pd.Series, meeting: pd.DataFrame, sales: pd.DataFrame, news: pd.DataFrame) -> str:
    name = str(row["customer_name"])
    news_md = _news_block(news)
    return f"""# {name} 방문 준비 보고서

## 1. 고객 현황
- 주소: {row.get("address") or "자료 없음"}
- 대표이사: {row.get("ceo_name") or "자료 없음"}
- 창립년도: {row.get("founded_year") or "자료 없음"}
- 종업원수: {row.get("employee_count") or "자료 없음"}
- 전년도 매출액: {row.get("prev_year_revenue") or "자료 없음"}
- 신용등급: {row.get("credit_rating") or "자료 없음"}
- 주요생산품목: {row.get("main_products") or "자료 없음"}
- 당사 구매 철강재: {row.get("purchased_steel") or "자료 없음"}
- 당사 매출액: {row.get("our_sales") or "자료 없음"}
- 상태: {row.get("status") or "-"} ({row.get("status_reason") or "-"})

## 2. 매출 및 구매 추이
- 첫 납품일: {format_date(row.get("first_sales_date")) or "자료 없음"}
- 최근 납품일: {format_date(row.get("latest_sales_date")) or "자료 없음"}
- 최근 매출: {format_amount(row.get("latest_sales_amount")) or "자료 없음"}

{_sales_block(sales, row["join_key"])}

## 3. 최근 방문 내용 및 요청사항
{_meetings_block(meeting, row["join_key"])}

## 4. 최근 뉴스 및 산업 동향
{news_md}

## 5. 영업기회
자료에 있는 뉴스의 '고객사에 미치는 영향'과 방문 요청사항을 기준으로 담당자가 검토한다. 입력 밖의 기회는 적지 않는다.

## 6. 위험요인
상태 근거: {row.get("status_reason") or "자료 없음"}
반복 요청과 구매 감소 여부는 config 기준이 있을 때만 판정한다.

## 7. 방문 시 확인사항
- 최근 방문일지상의 미해결 요청사항 진행 여부
- 선택 뉴스에서 언급된 영향이 실제 구매·납기에 미치는지

## 8. 근거
- customer_info, customer_sales, customer_meeting, customer_news
- 기준일: {reference_date().isoformat()}
"""


def generate_report(
    row: pd.Series,
    meeting: pd.DataFrame,
    sales: pd.DataFrame,
    news: pd.DataFrame,
) -> tuple[str, bool]:
    system_prompt = _read_system_prompt()
    user_prompt = build_user_prompt(row, meeting, sales, news)
    if not llm.api_key():
        return fallback_report(row, meeting, sales, news), False
    text = call_llm(system_prompt, user_prompt)
    return text, True
