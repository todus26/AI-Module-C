from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Item:
    id: int
    name: str
    quantity: float
    unit: str
    expiry: date | None
    category: str


@dataclass(frozen=True)
class Ingredient:
    name: str
    amount: str


@dataclass(frozen=True)
class Recipe:
    name: str
    time_min: int
    difficulty: str
    calories: int
    ingredients: tuple[Ingredient, ...]
    seasonings: tuple[Ingredient, ...]
    steps: tuple[str, ...]
    servings: int = 2
    source: str = "dataset"

    @classmethod
    def from_dict(cls, data: dict, source: str = "dataset") -> "Recipe":
        """재료는 [이름, 분량] 쌍 또는 {"name", "amount"} 객체 모두 허용한다."""

        def parse(entries) -> tuple[Ingredient, ...]:
            result = []
            for entry in entries:
                if isinstance(entry, dict):
                    result.append(Ingredient(str(entry["name"]), str(entry.get("amount", ""))))
                else:
                    result.append(Ingredient(str(entry[0]), str(entry[1]) if len(entry) > 1 else ""))
            return tuple(result)

        ingredients = parse(data["ingredients"])
        if not ingredients:
            raise ValueError("필수 재료가 비어 있습니다.")
        steps = tuple(str(s) for s in data["steps"])
        if not steps:
            raise ValueError("조리 순서가 비어 있습니다.")
        return cls(
            name=str(data["name"]).strip(),
            time_min=int(data["time_min"]),
            difficulty=str(data["difficulty"]),
            calories=int(data["calories"]),
            ingredients=ingredients,
            seasonings=parse(data.get("seasonings", [])),
            steps=steps,
            servings=int(data.get("servings", 2)),
            source=source,
        )
