"""거래처 수, 위치 여부, 상태 건수를 출력한다."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data_loader import load_all  # noqa: E402
from src.status import apply_status, condition_counts, status_counts  # noqa: E402


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    bundle = load_all()
    customers = apply_status(bundle.customers, bundle.sales, bundle.meeting)
    located = int(customers["has_location"].sum())
    missing = int((~customers["has_location"]).sum())
    print(f"거래처 수: {len(customers)}")
    print(f"위치 있음: {located}")
    print(f"위치 없음: {missing}")
    print("상태 건수:", status_counts(customers))
    print("조건별 건수:", condition_counts(customers, bundle.sales, bundle.meeting))
    print(customers[["customer_name", "has_location", "status", "status_reason"]].to_string(index=False))


if __name__ == "__main__":
    main()
