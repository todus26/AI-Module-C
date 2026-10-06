from pathlib import Path

from core.catalog import catalog_keys, is_staple
from core.normalize import normalize
from core.recipe_store import RecipeStore

DATA = Path(__file__).parent.parent / "data" / "recipes.json"
store = RecipeStore(DATA)


def test_dataset_has_about_fifty_unique_recipes():
    recipes = store.all()
    assert len(recipes) == 50
    assert len({r.name for r in recipes}) == 50


def test_every_recipe_has_valid_fields():
    for r in store.all():
        assert r.difficulty in {"쉬움", "보통", "어려움"}, r.name
        assert r.time_min > 0 and r.calories > 0, r.name
        assert len(r.steps) >= 3, r.name


def test_required_ingredients_are_in_catalog_and_seasonings_are_staples():
    keys = catalog_keys()
    for r in store.all():
        for ing in r.ingredients:
            assert normalize(ing.name) in keys, f"{r.name}: {ing.name}"
        for s in r.seasonings:
            assert is_staple(s.name), f"{r.name}: {s.name}"


def test_search_matches_name_and_ingredient():
    found = [r.name for r in store.search("김치찌개")]
    assert "김치찌개" in found and "참치김치찌개" in found and "된장찌개" not in found
    assert "계란말이" in [r.name for r in store.search("달걀")]
    assert len(store.search("")) == 50
