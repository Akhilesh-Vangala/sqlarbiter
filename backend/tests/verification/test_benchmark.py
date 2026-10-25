import json
import unittest

from sqlarbiter.evaluation.benchmark import corpus_manifest
from sqlarbiter.evaluation.benchmark import MANIFEST
from sqlarbiter.evaluation.benchmark import pass_at_k
from sqlarbiter.evaluation.benchmark import estimate_cost
from sqlarbiter.evaluation.benchmark_cases import benchmark_cases
from sqlarbiter.evaluation.evaluation import reference_outcome


class BenchmarkContractTests(unittest.TestCase):
    def test_manifest_is_frozen_and_private_snapshots_have_independent_truth(self):
        self.assertEqual(json.loads(MANIFEST.read_text()), corpus_manifest())
        cases = benchmark_cases()
        self.assertEqual(len(cases), 38)
        self.assertEqual(len({c.incident.case_id for c in cases}), 38)
        for case in cases[6:]:
            self.assertEqual(len(case.incident.sources), 2)
            self.assertNotIn(case.family, json.dumps(case.incident.contract))
            self.assertNotEqual(reference_outcome(case.incident, case.incident.sources[0]),
                                reference_outcome(case.incident, case.incident.sources[1]))
        calibration = {c.template_group for c in cases if c.split == "calibration"}
        evaluation = {c.template_group for c in cases if c.split == "evaluation"}
        self.assertFalse(calibration & evaluation)

    def test_pass_at_k_accounts_for_attempt_count_and_success_count(self):
        self.assertIsNone(pass_at_k(1, 1, 3))
        self.assertAlmostEqual(pass_at_k(1, 3, 1), 1 / 3)
        self.assertEqual(pass_at_k(1, 3, 3), 1)
        self.assertEqual(pass_at_k(0, 3, 3), 0)
        self.assertAlmostEqual(pass_at_k(2, 5, 3), 0.9)

    def test_unknown_billing_or_model_mismatch_never_becomes_zero_cost(self):
        rates = {"model": "test", "input_per_million": 2, "output_per_million": 10,
                 "cache_write_per_million": 2.5, "cache_read_per_million": 0.2}
        run = {"resolved_model": "test", "status": "completed", "usage": {
            "input_tokens": 1000000, "output_tokens": 1000000}}
        self.assertEqual(estimate_cost(run, rates), 12)
        self.assertIsNone(estimate_cost(dict(run, additional_billing_unknown=True), rates))
        self.assertIsNone(estimate_cost(dict(run, resolved_model="other"), rates))
