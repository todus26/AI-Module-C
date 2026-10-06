from datetime import date, timedelta

import pytest

import app
from core.inventory_store import InventoryStore


@pytest.fixture
def isolated_app(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "store", InventoryStore(tmp_path / "pantry.db"))
    monkeypatch.setattr(app, "today", lambda: date(2026, 10, 6))
    return app


def test_empty_fridge_shows_guidance_and_no_shortage(isolated_app):
    inventory, shortage, summary = isolated_app.render_inventory("전체")
    assert len(shortage) == 0
    assert "등록된 재료가 없습니다" in summary


def test_inventory_page_shows_expiring_and_shortage(isolated_app):
    store = isolated_app.store
    store.add("달걀", 4, "개", date(2026, 10, 8), "유제품·계란")
    store.add("대파", 1, "대", None, "채소")
    inventory, shortage, summary = isolated_app.render_inventory("전체")

    frame = inventory.data
    assert "임박 (D-2)" in frame["상태"].tolist()
    assert "임박 1개" in summary
    assert len(shortage) > 0
    assert "부족한 재료" in shortage.columns


def test_recipe_detail_marks_owned_and_missing(isolated_app):
    isolated_app.store.add("달걀", 4, "개", None, "유제품·계란")
    detail = app.recipe_detail(app.recipes.get("계란말이"), app.owned_names())
    assert "계란 4개 — 보유" in detail
    assert "당근 1/4개 — **부족**" in detail
    assert "조리 순서" in detail


def test_ai_without_key_degrades_gracefully(isolated_app, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    isolated_app.store.add("달걀", 1, "개", None, "유제품·계란")
    rows, mapping, note = isolated_app.run_ai()
    assert rows == [] and mapping == {}
    assert "사용할 수 없습니다" in note
