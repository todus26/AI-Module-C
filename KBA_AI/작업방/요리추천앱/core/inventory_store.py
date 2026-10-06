from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import date
from pathlib import Path

from core.models import Item
from core.normalize import normalize

_SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    quantity REAL NOT NULL,
    unit TEXT NOT NULL,
    expiry TEXT,
    category TEXT NOT NULL
)
"""


def _to_item(row: sqlite3.Row) -> Item:
    return Item(
        id=row["id"],
        name=row["name"],
        quantity=row["quantity"],
        unit=row["unit"],
        expiry=date.fromisoformat(row["expiry"]) if row["expiry"] else None,
        category=row["category"],
    )


class InventoryStore:
    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn:
            conn.execute(_SCHEMA)
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def add(
        self,
        name: str,
        quantity: float,
        unit: str,
        expiry: date | None,
        category: str,
    ) -> tuple[Item, bool]:
        """재료를 추가한다. 이름과 단위가 같은 재료가 있으면 수량을 합쳐 병합하고 (item, True)를 돌려준다."""
        name = (name or "").strip()
        if not name:
            raise ValueError("재료명을 입력하세요.")
        if quantity is None or quantity <= 0:
            raise ValueError("수량은 0보다 커야 합니다.")
        unit = (unit or "개").strip() or "개"
        category = (category or "기타").strip() or "기타"

        with closing(self._connect()) as conn:
            key = normalize(name)
            for row in conn.execute("SELECT * FROM items"):
                if normalize(row["name"]) == key and row["unit"] == unit:
                    existing = _to_item(row)
                    dates = [d for d in (existing.expiry, expiry) if d is not None]
                    merged_expiry = min(dates) if dates else None
                    conn.execute(
                        "UPDATE items SET quantity = ?, expiry = ? WHERE id = ?",
                        (existing.quantity + quantity, merged_expiry.isoformat() if merged_expiry else None, existing.id),
                    )
                    conn.commit()
                    return self.get(existing.id), True

            cursor = conn.execute(
                "INSERT INTO items (name, quantity, unit, expiry, category) VALUES (?, ?, ?, ?, ?)",
                (name, quantity, unit, expiry.isoformat() if expiry else None, category),
            )
            conn.commit()
            return self.get(cursor.lastrowid), False

    def get(self, item_id: int) -> Item | None:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
        return _to_item(row) if row else None

    def update(self, item_id: int, quantity: float, expiry: date | None) -> Item:
        if quantity is None or quantity <= 0:
            raise ValueError("수량은 0보다 커야 합니다.")
        if self.get(item_id) is None:
            raise ValueError("존재하지 않는 재료입니다.")
        with closing(self._connect()) as conn:
            conn.execute(
                "UPDATE items SET quantity = ?, expiry = ? WHERE id = ?",
                (quantity, expiry.isoformat() if expiry else None, item_id),
            )
            conn.commit()
        return self.get(item_id)

    def delete(self, item_id: int) -> bool:
        with closing(self._connect()) as conn:
            cursor = conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
            conn.commit()
            return cursor.rowcount > 0

    def list_items(self, category: str | None = None) -> list[Item]:
        """유통기한이 빠른 순으로 돌려준다. 기한 없는 재료는 맨 뒤다."""
        with closing(self._connect()) as conn:
            rows = conn.execute("SELECT * FROM items").fetchall()
        items = [_to_item(r) for r in rows]
        if category and category != "전체":
            items = [i for i in items if i.category == category]
        return sorted(items, key=lambda i: (i.expiry is None, i.expiry or date.max, i.name))
