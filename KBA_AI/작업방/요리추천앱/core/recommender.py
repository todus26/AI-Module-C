from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable

from core.expiry import STATUS_EXPIRED, STATUS_EXPIRING, expiry_status
from core.models import Item, Recipe
from core.normalize import normalize

READY = "바로 가능"
ALMOST = "조금 부족"
MAX_MISSING = 2


@dataclass(frozen=True)
class Recommendation:
    recipe: Recipe
    verdict: str
    missing: tuple[str, ...]
    expiring_used: tuple[str, ...]
    match_rate: float


def usable_items(inventory: Iterable[Item], today: date) -> list[Item]:
    """만료되지 않은 재료만 돌려준다."""
    return [i for i in inventory if expiry_status(i.expiry, today) != STATUS_EXPIRED]


def recommend(
    inventory: Iterable[Item], recipes: Iterable[Recipe], today: date
) -> list[Recommendation]:
    """재고로 만들 수 있거나 필수 재료가 1~2개 부족한 요리를 추천 순서대로 돌려준다.

    기본 양념(seasonings)은 항상 있다고 보고 매칭하지 않는다.
    필수 재료를 하나도 가지고 있지 않은 요리는 추천하지 않는다.
    정렬: 바로 가능 > 조금 부족, 같은 판정 안에서는 임박 재료를 많이 쓰는 순, 그다음 일치율 순.
    """
    items = usable_items(inventory, today)
    owned = {normalize(i.name) for i in items}
    expiring = {
        normalize(i.name): i.name
        for i in items
        if expiry_status(i.expiry, today) == STATUS_EXPIRING
    }

    results: list[Recommendation] = []
    for recipe in recipes:
        required = [(ing.name, normalize(ing.name)) for ing in recipe.ingredients]
        if not required:
            continue
        missing = tuple(name for name, key in required if key not in owned)
        if len(missing) > MAX_MISSING or len(missing) == len(required):
            continue
        expiring_used = tuple(
            expiring[key] for _, key in required if key in expiring
        )
        results.append(
            Recommendation(
                recipe=recipe,
                verdict=READY if not missing else ALMOST,
                missing=missing,
                expiring_used=expiring_used,
                match_rate=(len(required) - len(missing)) / len(required),
            )
        )

    results.sort(
        key=lambda r: (
            r.verdict != READY,
            -len(r.expiring_used),
            -r.match_rate,
            r.recipe.time_min,
            r.recipe.name,
        )
    )
    return results


def missing_summary(recommendations: Iterable[Recommendation]) -> list[tuple[str, list[str]]]:
    """'조금 부족' 요리에서 부족한 재료별로, 그 재료를 사면 만들 수 있게 되는 요리 이름을 모은다."""
    needed: dict[str, list[str]] = {}
    for rec in recommendations:
        if rec.verdict != ALMOST:
            continue
        for name in rec.missing:
            needed.setdefault(name, []).append(rec.recipe.name)
    return sorted(needed.items(), key=lambda kv: (-len(kv[1]), kv[0]))
