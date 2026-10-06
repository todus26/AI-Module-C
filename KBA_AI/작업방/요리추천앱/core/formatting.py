from __future__ import annotations

from datetime import date
from typing import Iterable

from core.expiry import status_label
from core.models import Item, Recipe
from core.normalize import normalize
from core.recommender import Recommendation

INVENTORY_HEADERS = ["ID", "재료", "수량", "단위", "유통기한", "상태", "분류"]
SHORTAGE_HEADERS = ["부족한 재료", "사면 만들 수 있는 요리"]
RECOMMEND_HEADERS = ["요리", "판정", "조리 시간(분)", "난이도", "칼로리(kcal)", "부족한 재료", "임박 재료 사용"]
RECIPE_HEADERS = ["요리", "조리 시간(분)", "난이도", "칼로리(kcal)", "필수 재료"]


def format_quantity(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:g}"


def inventory_rows(items: Iterable[Item], today: date) -> list[list]:
    return [
        [
            i.id,
            i.name,
            format_quantity(i.quantity),
            i.unit,
            i.expiry.isoformat() if i.expiry else "-",
            status_label(i.expiry, today),
            i.category,
        ]
        for i in items
    ]


def recommendation_rows(recs: Iterable[Recommendation]) -> list[list]:
    return [
        [
            r.recipe.name,
            r.verdict,
            r.recipe.time_min,
            r.recipe.difficulty,
            r.recipe.calories,
            ", ".join(r.missing) or "-",
            ", ".join(r.expiring_used) or "-",
        ]
        for r in recs
    ]


def recipe_rows(recipes: Iterable[Recipe]) -> list[list]:
    return [
        [
            r.name,
            r.time_min,
            r.difficulty,
            r.calories,
            ", ".join(i.name for i in r.ingredients),
        ]
        for r in recipes
    ]


def shortage_rows(summary: list[tuple[str, list[str]]]) -> list[list]:
    return [[name, ", ".join(recipes)] for name, recipes in summary]


def recipe_detail(recipe: Recipe, owned_names: set[str] | None = None) -> str:
    """선택한 요리의 재료 분량과 조리 순서를 마크다운으로 만든다.

    owned_names(정규화된 재료명 집합)를 주면 필수 재료마다 보유/부족을 표시한다.
    """
    badge = "  [AI 추천]" if recipe.source == "ai" else ""
    lines = [
        f"### {recipe.name}{badge}",
        f"{recipe.servings}인분 | 조리 시간 {recipe.time_min}분 | 난이도 {recipe.difficulty} | 약 {recipe.calories}kcal (1인분)",
        "",
        "**재료**",
    ]
    for ing in recipe.ingredients:
        mark = ""
        if owned_names is not None:
            mark = " — 보유" if normalize(ing.name) in owned_names else " — **부족**"
        lines.append(f"- {ing.name} {ing.amount}{mark}")
    if recipe.seasonings:
        lines += ["", "**기본 양념**"]
        lines += [f"- {s.name} {s.amount}" for s in recipe.seasonings]
    lines += ["", "**조리 순서**"]
    lines += [f"{n}. {step}" for n, step in enumerate(recipe.steps, start=1)]
    return "\n".join(lines)
