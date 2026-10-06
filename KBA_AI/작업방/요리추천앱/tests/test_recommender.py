from datetime import date, timedelta
from pathlib import Path

from core.models import Ingredient, Item, Recipe
from core.recipe_store import RecipeStore
from core.recommender import ALMOST, READY, missing_summary, recommend

TODAY = date(2026, 10, 6)
DATA = Path(__file__).parent.parent / "data" / "recipes.json"


def item(name, days=None, id=1):
    expiry = TODAY + timedelta(days=days) if days is not None else None
    return Item(id=id, name=name, quantity=1, unit="개", expiry=expiry, category="기타")


def recipe(name, required, seasonings=(), time_min=20):
    return Recipe(
        name=name,
        time_min=time_min,
        difficulty="쉬움",
        calories=300,
        ingredients=tuple(Ingredient(n, "1") for n in required),
        seasonings=tuple(Ingredient(n, "1") for n in seasonings),
        steps=("조리",),
    )


def names(recs):
    return [r.recipe.name for r in recs]


def test_ready_when_all_required_ingredients_owned():
    recs = recommend([item("계란"), item("대파")], [recipe("계란파볶음", ["계란", "대파"])], TODAY)
    assert recs[0].verdict == READY
    assert recs[0].missing == ()


def test_almost_when_one_or_two_missing_and_names_reported():
    r = recipe("A", ["계란", "대파", "양파"])
    one = recommend([item("계란"), item("대파")], [r], TODAY)[0]
    two = recommend([item("계란")], [r], TODAY)[0]
    assert (one.verdict, one.missing) == (ALMOST, ("양파",))
    assert (two.verdict, set(two.missing)) == (ALMOST, {"대파", "양파"})


def test_excluded_when_three_or_more_missing():
    r = recipe("A", ["계란", "대파", "양파", "당근"])
    assert recommend([item("계란")], [r], TODAY) == []


def test_seasonings_do_not_affect_matching():
    r = recipe("A", ["계란"], seasonings=["소금", "간장", "참기름"])
    assert recommend([item("계란")], [r], TODAY)[0].verdict == READY


def test_expired_items_are_not_used_for_matching():
    r = recipe("A", ["계란", "대파"])
    rec = recommend([item("계란"), item("대파", days=-1)], [r], TODAY)[0]
    assert rec.verdict == ALMOST
    assert rec.missing == ("대파",)


def test_item_expiring_today_is_still_usable():
    rec = recommend([item("계란", days=0)], [recipe("A", ["계란"])], TODAY)[0]
    assert rec.verdict == READY
    assert rec.expiring_used == ("계란",)


def test_expiring_ingredient_users_come_first_within_same_verdict():
    inventory = [item("계란", days=2), item("대파"), item("양파")]
    recs = recommend(
        inventory,
        [recipe("대파양파", ["대파", "양파"]), recipe("계란대파", ["계란", "대파"])],
        TODAY,
    )
    assert names(recs) == ["계란대파", "대파양파"]
    assert recs[0].expiring_used == ("계란",)


def test_ready_comes_before_almost_even_if_almost_uses_expiring_item():
    inventory = [item("계란", days=1), item("대파")]
    recs = recommend(
        inventory,
        [recipe("계란양파", ["계란", "양파"]), recipe("대파만", ["대파"])],
        TODAY,
    )
    assert names(recs) == ["대파만", "계란양파"]


def test_synonyms_match_same_ingredient():
    recs = recommend([item("달걀"), item("파")], [recipe("계란파", ["계란", "대파"])], TODAY)
    assert recs[0].verdict == READY


def test_spacing_and_case_are_ignored():
    recs = recommend([item("  스파게티 면 ")], [recipe("A", ["스파게티면"])], TODAY)
    assert recs[0].verdict == READY


def test_empty_inventory_gives_no_recommendations():
    recipes = [recipe("A", ["계란", "대파", "양파"]), recipe("B", ["계란"]), recipe("C", ["계란", "대파"])]
    assert recommend([], recipes, TODAY) == []


def test_recipe_sharing_no_ingredient_with_inventory_is_not_recommended():
    assert recommend([item("두부")], [recipe("A", ["계란", "대파"])], TODAY) == []


def test_missing_summary_groups_recipes_by_missing_ingredient():
    inventory = [item("계란")]
    recs = recommend(
        inventory,
        [recipe("A", ["계란", "대파"]), recipe("B", ["계란", "대파", "양파"]), recipe("C", ["계란"])],
        TODAY,
    )
    summary = dict(missing_summary(recs))
    assert summary["대파"] == ["A", "B"]
    assert summary["양파"] == ["B"]


def test_real_dataset_recommends_with_a_typical_fridge():
    store = RecipeStore(DATA)
    inventory = [item(n) for n in ["계란", "대파", "당근", "밥", "김치"]]
    recs = recommend(inventory, store.all(), TODAY)
    ready = {r.recipe.name for r in recs if r.verdict == READY}
    assert {"계란말이", "계란볶음밥", "김치볶음밥"} <= ready
