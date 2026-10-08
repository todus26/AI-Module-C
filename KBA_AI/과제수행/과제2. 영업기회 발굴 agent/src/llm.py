"""LLM 호출. API 키는 환경변수 또는 .env에서 읽는다."""

from __future__ import annotations

import os

from dotenv import load_dotenv

import config

load_dotenv(config.BASE_DIR / ".env")


def api_key() -> str:
    return (os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip()


def model_name() -> str:
    return os.getenv("LLM_MODEL", "gpt-4o-mini")


def complete(messages: list[dict], temperature: float = 0.2) -> str:
    key = api_key()
    if not key:
        raise RuntimeError("LLM API 키가 없습니다. OPENAI_API_KEY 또는 LLM_API_KEY를 확인하세요.")
    from openai import OpenAI

    client = OpenAI(api_key=key, base_url=os.getenv("LLM_BASE_URL") or None)
    response = client.chat.completions.create(
        model=model_name(),
        temperature=temperature,
        messages=messages,
    )
    text = response.choices[0].message.content if response.choices else ""
    if not text:
        raise RuntimeError("LLM이 빈 응답을 반환했습니다.")
    return text.strip()
