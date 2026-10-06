from datetime import date

import pytest

from core.expiry import STATUS_EXPIRED, STATUS_EXPIRING, STATUS_NONE, STATUS_NORMAL, expiry_status, parse_expiry
from core.inventory_store import InventoryStore

TODAY = date(2026, 10, 6)


@pytest.fixture
def store(tmp_path):
    return InventoryStore(tmp_path / "pantry.db")


def test_add_list_update_delete(store):
    item, merged = store.add("양파", 2, "개", None, "채소")
    assert not merged
    assert [i.name for i in store.list_items()] == ["양파"]

    updated = store.update(item.id, 5, date(2026, 10, 10))
    assert updated.quantity == 5 and updated.expiry == date(2026, 10, 10)

    assert store.delete(item.id)
    assert store.list_items() == []


def test_data_persists_across_instances(tmp_path):
    InventoryStore(tmp_path / "p.db").add("두부", 1, "모", None, "두부·가공식품")
    assert [i.name for i in InventoryStore(tmp_path / "p.db").list_items()] == ["두부"]


def test_duplicate_is_merged_and_keeps_earlier_expiry(store):
    store.add("계란", 3, "개", date(2026, 10, 20), "유제품·계란")
    item, merged = store.add("달걀", 2, "개", date(2026, 10, 10), "유제품·계란")
    assert merged and item.quantity == 5 and item.expiry == date(2026, 10, 10)
    assert len(store.list_items()) == 1


def test_same_name_with_different_unit_is_kept_separate(store):
    store.add("우유", 1, "팩", None, "유제품·계란")
    store.add("우유", 500, "ml", None, "유제품·계란")
    assert len(store.list_items()) == 2


@pytest.mark.parametrize("name,qty", [("", 1), ("  ", 1), ("양파", 0), ("양파", -1)])
def test_invalid_input_is_rejected(store, name, qty):
    with pytest.raises(ValueError):
        store.add(name, qty, "개", None, "채소")
    assert store.list_items() == []


def test_list_is_sorted_by_expiry_with_no_expiry_last(store):
    store.add("A", 1, "개", None, "기타")
    store.add("B", 1, "개", date(2026, 10, 9), "기타")
    store.add("C", 1, "개", date(2026, 10, 7), "기타")
    assert [i.name for i in store.list_items()] == ["C", "B", "A"]


def test_category_filter(store):
    store.add("양파", 1, "개", None, "채소")
    store.add("돼지고기", 1, "g", None, "육류")
    assert [i.name for i in store.list_items("육류")] == ["돼지고기"]
    assert len(store.list_items("전체")) == 2


def test_expiry_status_boundaries():
    d = lambda n: date.fromordinal(TODAY.toordinal() + n)  # noqa: E731
    assert expiry_status(None, TODAY) == STATUS_NONE
    assert expiry_status(d(-1), TODAY) == STATUS_EXPIRED
    assert expiry_status(d(0), TODAY) == STATUS_EXPIRING
    assert expiry_status(d(3), TODAY) == STATUS_EXPIRING
    assert expiry_status(d(4), TODAY) == STATUS_NORMAL


def test_parse_expiry():
    assert parse_expiry("") is None
    assert parse_expiry("2026-10-12") == date(2026, 10, 12)
    with pytest.raises(ValueError):
        parse_expiry("10/12")
