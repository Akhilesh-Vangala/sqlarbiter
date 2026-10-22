"""Separate benchmark faults from agent accuracy; authored cases are not held-out."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vdir.evaluation.benchmark import PRELIVE_MANIFEST, classify_outcome, corpus_manifest, estimate_cost, run_benchmark
from vdir.evaluation.prelive_cases import prelive_cases
from fixtures.pricing import PRICE


class PreliveEvaluationTests(unittest.TestCase):
    def test_frozen_capabilities_run_against_independent_references(self):
        self.assertEqual(json.loads(PRELIVE_MANIFEST.read_text()), corpus_manifest("prelive"))
        with tempfile.TemporaryDirectory() as tmp:
            report = run_benchmark(Path(tmp)/"benchmark", engine="sqlite", suite="prelive")
        self.assertEqual(report["summary"]["scored_attempts"], 8)
        self.assertEqual(report["summary"]["pass_at_1"], 1)
        self.assertIsNone(report["summary"]["pass_at_3"])
        self.assertEqual(report["summary"]["outcomes"]["clarification"], 2)
        self.assertIn("not unseen", report["scope"])
        self.assertEqual(len({r["run_id"] for r in report["records"]}), 8)

    def test_evaluator_fault_is_recorded_without_becoming_a_model_failure(self):
        with tempfile.TemporaryDirectory() as tmp, patch("vdir.evaluation.benchmark.grade", side_effect=ValueError("private-invalid-oracle")):
            report = run_benchmark(Path(tmp)/"benchmark", engine="sqlite", suite="prelive",
                                   case_ids=[prelive_cases()[0].incident.case_id])
        self.assertEqual(report["summary"]["outcomes"], {"evaluator_error": 1})
        self.assertEqual(report["summary"]["scored_attempts"], 0)
        self.assertIsNone(report["summary"]["pass_at_1"])
        self.assertNotIn("private-invalid-oracle", json.dumps(report))

    def test_execution_refusal_and_incorrect_result_have_distinct_outcomes(self):
        self.assertEqual(classify_outcome({"error": "failure"}, {"passed": False}), "execution_error")
        self.assertEqual(classify_outcome({"decision": {"status": "candidate"}}, {"passed": False}), "verification_failed")
        self.assertEqual(classify_outcome({"decision": {"status": "needs_information"}}, {"passed": True}), "clarification")

    def test_missing_and_invalid_usage_cannot_be_reported_as_free_generation(self):
        for usage in ({}, {"input_tokens": 1}, {"input_tokens": True, "output_tokens": 2}, {"input_tokens": -1, "output_tokens": 2}):
            with self.subTest(usage=usage):
                self.assertIsNone(estimate_cost({"status": "completed", "resolved_model": PRICE["model"], "usage": usage}, PRICE))
