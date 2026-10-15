import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from vdir.spending import SpendLedger, SpendRejected, dollars

PRICE = {"model": "configured-model", "verified_at": "2026-10-12", "source_url": "https://example.test/pricing",
         "input_per_million": 2, "output_per_million": 10, "cache_write_per_million": 4, "cache_read_per_million": .1}


class SpendTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "ledger.sqlite"

    def tearDown(self):
        self.temp.cleanup()

    def test_settlement_releases_unused_allowance_and_cache_categories_are_separate(self):
        ledger = SpendLedger(self.path, PRICE)
        identity = ledger.reserve("one", "configured-model", 1000, 1000)
        self.assertEqual(ledger.summary()["accounted_usd"], .014)
        self.assertEqual(ledger.settle(identity, {"input_tokens": 100, "output_tokens": 10, "cache_creation_input_tokens": 5, "cache_read_input_tokens": 10}), 321)
        self.assertEqual(ledger.summary()["accounted_usd"], .000321)
        with self.assertRaises(SpendRejected):
            ledger.settle(identity, {"input_tokens": 0, "output_tokens": 0})

    def test_unknown_request_survives_restart_and_cannot_be_released_by_settlement(self):
        ledger = SpendLedger(self.path, PRICE, ".02", ".02")
        identity = ledger.reserve("one", "configured-model", 1000, 1000)
        ledger.uncertain(identity)
        reopened = SpendLedger(self.path, PRICE, ".02", ".02")
        self.assertEqual(reopened.summary()["states"]["unknown"]["requests"], 1)
        with self.assertRaises(SpendRejected):
            reopened.reserve("two", "configured-model", 1000, 1000)
        with self.assertRaises(SpendRejected):
            reopened.settle(identity, {"input_tokens": 0, "output_tokens": 0})

    def test_invalid_limits_rate_and_model_fail_closed_and_policy_cannot_silently_reset(self):
        for value in ("nan", "inf", "0", "-1", "0.0000001", "bad"):
            with self.assertRaises(SpendRejected):
                dollars(value)
        with self.assertRaises(SpendRejected):
            SpendLedger(self.path, dict(PRICE, output_per_million="NaN"))
        ledger = SpendLedger(self.path, PRICE)
        with self.assertRaises(SpendRejected):
            ledger.reserve("one", "different-model", 1, 1)
        with self.assertRaises(SpendRejected):
            SpendLedger(self.path, PRICE, "2", "5")
        with self.assertRaises(SpendRejected):
            ledger.cost({"input_tokens": True, "output_tokens": 2})

    def test_overrun_is_fully_accounted_and_blocks_subsequent_calls(self):
        ledger = SpendLedger(self.path, PRICE)
        identity = ledger.reserve("one", "configured-model", 1, 1)
        with self.assertRaises(SpendRejected):
            ledger.settle(identity, {"input_tokens": 100, "output_tokens": 100})
        self.assertEqual(ledger.summary()["states"]["overrun"]["usd"], .0012)
        with self.assertRaises(SpendRejected):
            ledger.reserve("two", "configured-model", 1, 1)

    def test_independent_processes_cannot_overadmit_the_shared_allowance(self):
        SpendLedger(self.path, PRICE, "1", ".05")
        script = '''import json,sys
from vdir.spending import SpendLedger,SpendRejected
ledger=SpendLedger(sys.argv[1],json.loads(sys.argv[2]),"1",".05")
try:
 ledger.reserve(sys.argv[3],"configured-model",1000,1000)
 print("admitted")
except SpendRejected:
 print("rejected")
'''
        def execute(index):
            return subprocess.check_output([sys.executable, "-c", script, str(self.path), json.dumps(PRICE), str(index)], text=True, env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[2] / "backend" / "src")}).strip()
        with ThreadPoolExecutor(max_workers=8) as pool:
            outcomes = list(pool.map(execute, range(8)))
        self.assertEqual(outcomes.count("admitted"), 3)
        self.assertEqual(outcomes.count("rejected"), 5)
        self.assertAlmostEqual(SpendLedger(self.path, PRICE, "1", ".05").summary()["accounted_usd"], .042)
