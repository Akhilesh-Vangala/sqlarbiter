"""Separate benchmark faults from agent accuracy; authored cases are not held-out."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlarbiter.evaluation.benchmark import (
    SAFETY_MANIFEST,
    classify_outcome,
    corpus_manifest,
    estimate_cost,
    main,
    run_benchmark,
)
from sqlarbiter.evaluation.safety_cases import safety_cases
from fixtures.pricing import PRICE


class SafetyEvaluationTests(unittest.TestCase):
    def test_frozen_capabilities_run_against_independent_references(self):
        self.assertEqual(json.loads(SAFETY_MANIFEST.read_text()), corpus_manifest("safety"))
        with tempfile.TemporaryDirectory() as tmp:
            report = run_benchmark(Path(tmp) / "benchmark", engine="sqlite", suite="safety")
        self.assertEqual(report["summary"]["scored_attempts"], 8)
        self.assertEqual(report["summary"]["pass_at_1"], 1)
        self.assertIsNone(report["summary"]["pass_at_3"])
        self.assertTrue(report["summary"]["valid_evaluation"])
        self.assertEqual(report["summary"]["outcomes"]["clarification"], 2)
        self.assertIn("not unseen", report["scope"])
        self.assertEqual(len({r["run_id"] for r in report["records"]}), 8)

    def test_evaluator_fault_is_recorded_without_becoming_a_model_failure(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch(
                "sqlarbiter.evaluation.benchmark.grade",
                side_effect=ValueError("private-invalid-oracle"),
            ),
        ):
            report = run_benchmark(
                Path(tmp) / "benchmark",
                engine="sqlite",
                suite="safety",
                case_ids=[safety_cases()[0].incident.case_id],
            )
        self.assertEqual(report["summary"]["outcomes"], {"evaluator_error": 1})
        self.assertEqual(report["summary"]["scored_attempts"], 0)
        self.assertFalse(report["summary"]["valid_evaluation"])
        self.assertIsNone(report["summary"]["pass_at_1"])
        self.assertNotIn("private-invalid-oracle", json.dumps(report))

    def test_execution_refusal_and_incorrect_result_have_distinct_outcomes(self):
        self.assertEqual(
            classify_outcome({"error": "failure"}, {"passed": False}), "execution_error"
        )
        self.assertEqual(
            classify_outcome({"decision": {"status": "candidate"}}, {"passed": False}),
            "verification_failed",
        )
        self.assertEqual(
            classify_outcome({"decision": {"status": "needs_information"}}, {"passed": True}),
            "clarification",
        )

    def test_missing_and_invalid_usage_cannot_be_reported_as_free_generation(self):
        for usage in (
            {},
            {"input_tokens": 1},
            {"input_tokens": True, "output_tokens": 2},
            {"input_tokens": -1, "output_tokens": 2},
        ):
            with self.subTest(usage=usage):
                self.assertIsNone(
                    estimate_cost(
                        {"status": "completed", "resolved_model": PRICE["model"], "usage": usage},
                        PRICE,
                    )
                )

    def test_cli_does_not_announce_success_when_scored_accuracy_hides_an_evaluator_fault(self):
        with (
            patch("sqlarbiter.evaluation.benchmark.load_local_configuration"),
            patch("sys.argv", ["benchmark", "--output", "unused-test-output"]),
            patch(
                "sqlarbiter.evaluation.benchmark.run_benchmark",
                return_value={
                    "summary": {
                        "pass_at_1": 1.0,
                        "valid_evaluation": False,
                        "outcomes": {"verified_repair": 7, "evaluator_error": 1},
                    }
                },
            ),
            patch("builtins.print"),
            self.assertRaises(SystemExit) as caught,
        ):
            main()
        self.assertEqual(caught.exception.code, 1)
