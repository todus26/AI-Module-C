from __future__ import annotations

import json
import os

from core.models import Recipe

DEFAULT_MODEL = "gpt-4o-mini"

_SYSTEM_PROMPT = """너는 한국 가정식 요리 전문가다. 사용자가 가진 재료로 만들 수 있는 요리를 추천한다.
반드시 아래 JSON 형식으로만 답한다. 다른 설명은 쓰지 않는다.
{"recipes": [{
  "name": "요리 이름",
  "servings": 2,
  "time_min": 20,
  "difficulty": "쉬움|보통|어려움 중 하나",
  "calories": 1인분 기준 대략 kcal 정수,
  "ingredients": [{"name": "재료명", "amount": "분량"}],
  "seasonings": [{"name": "양념명", "amount": "분량"}],
  "steps": ["조리 순서 1", "조리 순서 2"]
}]}
규칙: ingredients에는 사용자가 가진 재료 위주로 넣고, 소금/간장/식용유 같은 기본 양념은 seasonings에 넣는다."""


class AiUnavailableError(RuntimeError):
    """API 키가 없거나 OpenAI 패키지를 쓸 수 없을 때."""


class AiGenerationError(RuntimeError):
    """호출 또는 응답 해석에 실패했을 때."""


def ai_available() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY"))


def parse_recipes(content: str) -> list[Recipe]:
    try:
        data = json.loads(content)
        raw = data["recipes"]
        return [Recipe.from_dict(r, source="ai") for r in raw]
    except (ValueError, KeyError, TypeError, IndexError) as exc:
        raise AiGenerationError(f"AI 응답을 해석하지 못했습니다: {exc}") from exc


def generate_recipes(
    ingredient_names: list[str], count: int = 2, client=None, model: str | None = None
) -> list[Recipe]:
    if not ingredient_names:
        raise AiGenerationError("재료가 없어 레시피를 만들 수 없습니다.")

    if client is None:
        if not ai_available():
            raise AiUnavailableError("OPENAI_API_KEY 환경변수가 설정되어 있지 않습니다.")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise AiUnavailableError("openai 패키지가 설치되어 있지 않습니다.") from exc
        client = OpenAI()

    model = model or os.environ.get("OPENAI_MODEL", DEFAULT_MODEL)
    try:
        response = client.chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"가진 재료: {', '.join(ingredient_names)}\n"
                    f"이 재료로 만들 수 있는 요리 {count}개를 추천해줘.",
                },
            ],
            timeout=30,
        )
        content = response.choices[0].message.content
    except Exception as exc:  # noqa: BLE001 - 네트워크/인증 등 모든 실패를 사용자 메시지로 바꾼다
        raise AiGenerationError(f"AI 호출에 실패했습니다: {exc}") from exc
    return parse_recipes(content)
