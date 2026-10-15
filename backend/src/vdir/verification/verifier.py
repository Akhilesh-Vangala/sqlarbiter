"""Semantic output comparisons; no exact SQL patch matching."""
from dataclasses import dataclass
from typing import Tuple

from vdir.verification.reference import expected_revenue
from vdir.verification.runner import QueryRejected
from vdir.verification.runner import run_query


@dataclass(frozen=True)
class Check:
    snapshot_id: str
    passed: bool
    problems: Tuple[str, ...]


def verify(snapshot, sql):
    # Invalid reference sources must fail the evaluator, not score an agent failure.
    expected = expected_revenue(snapshot)
    try:
        columns, rows = run_query(snapshot, sql)
        if columns != ("business_date", "category", "revenue_cents"):
            return Check(snapshot.snapshot_id, False, ("Output schema does not match contract",))
        actual = {}
        for day, category, amount in rows:
            if not isinstance(day, str) or not isinstance(category, str) or type(amount) is not int:
                return Check(snapshot.snapshot_id, False, ("Output has invalid field types",))
            key = (day, category)
            if key in actual:
                return Check(snapshot.snapshot_id, False, ("Duplicate output key",))
            actual[key] = amount
        problems = []
        for key in sorted(expected.keys() | actual.keys()):
            if key not in actual:
                problems.append("Missing group: %s/%s" % key)
            elif key not in expected:
                problems.append("Unexpected group: %s/%s" % key)
            elif actual[key] != expected[key]:
                problems.append("%s/%s expected %d cents, got %d" %
                                (key[0], key[1], expected[key], actual[key]))
        return Check(snapshot.snapshot_id, not problems, tuple(problems))
    except QueryRejected as error:
        return Check(snapshot.snapshot_id, False, ("Execution rejected: " + str(error),))


def verify_suite(cases, sql):
    cases = tuple(cases)
    if not cases:
        raise ValueError("A verification suite cannot be empty")
    return tuple(verify(case, sql) for case in cases)
