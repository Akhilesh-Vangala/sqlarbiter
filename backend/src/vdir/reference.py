"""Evaluator-only reference calculation, independent of transformation SQL.

Future agent processes must not receive this module or its expected results.
The current local demo has no agent and does not enforce process separation.
"""
from collections import defaultdict


def expected_revenue(snapshot):
    orders = {}
    for order_id, day, status in snapshot.orders:
        if order_id in orders:
            raise ValueError("Ambiguous duplicate order identity")
        orders[order_id] = (day, status)
    versions = {}
    latest = {}
    for product_id, version, category in snapshot.products:
        if (product_id, version) in versions:
            raise ValueError("Ambiguous duplicate product version")
        versions[(product_id, version)] = category
        if product_id not in latest or version > latest[product_id][0]:
            latest[product_id] = (version, category)
    totals = defaultdict(int)
    seen_items = set()
    for item_id, order_id, product_id, amount in snapshot.items:
        if item_id in seen_items:
            raise ValueError("Ambiguous duplicate item identity")
        seen_items.add(item_id)
        if type(amount) is not int or amount < 0:
            raise ValueError("Amounts must be nonnegative integer cents")
        if order_id not in orders or product_id not in latest:
            raise ValueError("Missing authoritative source relationship")
        day, status = orders[order_id]
        if status == "completed":
            category = latest[product_id][1]
            totals[(day, category)] += amount
    return dict(totals)
