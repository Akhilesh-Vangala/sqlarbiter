"""Missing provider usage must never masquerade as a zero-token round."""

import asyncio
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "agent/investigator"))
from sqlarbiter.domain.cases import incidents
from sqlarbiter.evaluation.evaluation import export_workspace
from model import investigate as linear, InvestigationFailed
from graph import investigate as graph, Receipts
from tools import EvidenceTools

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fixtures.model_fixtures import ScriptedClient, completion, call


class UsageBoundaryTests(unittest.TestCase):
    def test_both_controllers_reject_missing_partial_boolean_and_negative_usage(self):
        for runtime in [linear, graph]:
            for usage in [
                None,
                {},
                {"input_tokens": 20},
                {"output_tokens": 10},
                {"input_tokens": True, "output_tokens": 1},
                {"input_tokens": -1, "output_tokens": 1},
            ]:
                with (
                    self.subTest(runtime=runtime.__module__, usage=usage),
                    tempfile.TemporaryDirectory() as tmp,
                ):
                    workspace = export_workspace(incidents()[4], Path(tmp) / "evidence")
                    response = completion([call("contract", {})])
                    response["usage"] = usage
                    with self.assertRaisesRegex(InvestigationFailed, "usage"):
                        asyncio.run(runtime(EvidenceTools(workspace), ScriptedClient([response])))

    def test_partial_receipt_keeps_known_usage_and_flags_billing_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            receipts = Receipts(Path(tmp))
            receipts.begin("model-1")
            receipts.complete("model-1", {"result": {"usage": {"input_tokens": 20}}})
            usage, unknown = receipts.accounting()
            self.assertEqual(usage, {"input_tokens": 20, "output_tokens": 0})
            self.assertTrue(unknown)
