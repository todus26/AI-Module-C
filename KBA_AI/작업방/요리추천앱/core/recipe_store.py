from __future__ import annotations

import json
from pathlib import Path

from core.models import Recipe
from core.normalize import normalize


class RecipeStore:
    def __init__(self, path: str | Path):
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        self._recipes = [Recipe.from_dict(r) for r in raw]
        self._by_name = {r.name: r for r in self._recipes}

    def all(self) -> list[Recipe]:
        return list(self._recipes)

    def get(self, name: str) -> Recipe | None:
        return self._by_name.get(name)

    def search(self, query: str) -> list[Recipe]:
        """요리 이름 또는 필수 재료에 검색어가 포함된 레시피를 찾는다."""
        query = (query or "").strip()
        if not query:
            return self.all()
        key = normalize(query)
        found = []
        for recipe in self._recipes:
            in_name = query in recipe.name
            in_ingredients = any(
                key in normalize(i.name) or query in i.name for i in recipe.ingredients
            )
            if in_name or in_ingredients:
                found.append(recipe)
        return found
