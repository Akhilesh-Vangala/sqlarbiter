"""Original controlled snapshots. No real customer data is used."""

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class Snapshot:
    snapshot_id: str
    # order_id, business_date, status
    orders: Tuple[Tuple[str, str, str], ...]
    # item_id, order_id, product_id, amount_cents
    items: Tuple[Tuple[str, str, str, int], ...]
    # product_id, version, category
    products: Tuple[Tuple[str, int, str], ...]


def snapshots():
    """Development cases, deliberately small; not a broad held-out benchmark."""
    return (
        Snapshot(
            "incident",
            (
                ("o1", "2026-09-01", "completed"),
                ("o2", "2026-09-01", "completed"),
                ("o3", "2026-09-01", "canceled"),
            ),
            (("i1", "o1", "p1", 1200), ("i2", "o2", "p2", 800), ("i3", "o3", "p1", 9999)),
            (("p1", 1, "home"), ("p1", 2, "home"), ("p2", 1, "books"), ("p2", 2, "books")),
        ),
        Snapshot(
            "regression-equal-amounts",
            (
                ("o4", "2026-09-02", "completed"),
                ("o5", "2026-09-02", "completed"),
                ("o6", "2026-09-02", "pending"),
            ),
            (
                ("i4", "o4", "p1", 1200),
                ("i5", "o5", "p1", 1200),
                ("i6", "o4", "p2", 500),
                ("i7", "o6", "p2", 8888),
            ),
            (("p1", 1, "home"), ("p1", 2, "home"), ("p2", 1, "books")),
        ),
        Snapshot(
            "regression-category-change",
            (("o7", "2026-09-03", "completed"), ("o8", "2026-09-04", "completed")),
            (("i8", "o7", "p1", 700), ("i9", "o8", "p1", 900), ("i10", "o8", "p2", 300)),
            (("p1", 1, "home"), ("p1", 2, "electronics"), ("p2", 1, "books")),
        ),
    )
