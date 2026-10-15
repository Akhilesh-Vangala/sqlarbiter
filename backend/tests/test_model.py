import asyncio
import json
import os
import sys
import tempfile
import unittest

from pathlib import Path
from unittest.mock import patch

from vdir.cases import incidents
from vdir.evaluation import export_workspace, grade, evaluate_all

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend" / "investigator_runtime"))
from model import AnthropicClient, InvestigationFailed, investigate
from tools import EvidenceTools


def completion(calls, stop="tool_use"):
    return {"stop_reason": stop, "content": calls,
            "usage": {"input_tokens": 20, "output_tokens": 10}}


def call(name, params, identity="tool-1"):
    return {"type": "tool_use", "name": name, "input": params, "id": identity}


class ScriptedClient:
    def __init__(self, steps):
        self.steps = iter(steps)
        self.requests = []

    async def complete(self, messages, definitions, max_tokens=2048):
        self.requests.append(json.loads(json.dumps(messages)))
        step = next(self.steps)
        return step(messages) if callable(step) else step


class ModelInvestigatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.case = incidents()[4]
        self.tools = EvidenceTools(export_workspace(self.case, self.root / "evidence"))

    def tearDown(self):
        self.temp.cleanup()

    def finish(self, messages):
        evidence = json.loads(messages[-1]["content"][0]["content"])["evidence_id"]
        return completion([call("finish", {
            "status": "no_change", "explanation": "The current transformation satisfies this contract.",
            "evidence_ids": [evidence]})])

    def test_tool_use_transcript_is_replayed_and_graded(self):
        client = ScriptedClient([
            completion([call("contract", {})]),
            completion([call("query", {"sql": self.case.current_sql})]), self.finish])
        response = asyncio.run(investigate(self.tools, client))
        self.assertTrue(grade(self.case, response, self.root / "grading")["passed"])
        self.assertEqual(response["model_run"]["rounds"], 3)
        self.assertEqual(response["model_run"]["usage"], {"input_tokens": 60, "output_tokens": 30})
        self.assertEqual(response["model_run"]["status"], "completed")
        assistant = client.requests[-1][-2]
        self.assertEqual(assistant["role"], "assistant")
        self.assertEqual(client.requests[-1][-1]["content"][0]["tool_use_id"], "tool-1")

    def test_rejected_tool_is_returned_to_model_as_error(self):
        client = ScriptedClient([completion([call("read_file", {"path": "reference.py"})]),
                                 completion([call("contract", {})]), self.finish])
        asyncio.run(investigate(self.tools, client))
        self.assertTrue(client.requests[1][-1]["content"][0]["is_error"])
        self.assertFalse(self.tools.trace[0]["ok"])

    def test_invented_evidence_cannot_be_submitted(self):
        client = ScriptedClient([completion([call("finish", {
            "status": "no_change", "explanation": "Claim", "evidence_ids": ["ev-invented"]})])])
        with self.assertRaisesRegex(InvestigationFailed, "invented"):
            asyncio.run(investigate(self.tools, client))

    def test_finish_with_evidence_calls_is_rejected(self):
        client = ScriptedClient([completion([call("contract", {}, "one"),
                                            call("finish", {}, "two")])])
        with self.assertRaisesRegex(InvestigationFailed, "separately"):
            asyncio.run(investigate(self.tools, client))

    def test_truncation_refusal_invalid_usage_and_identity_fail_closed(self):
        responses = [completion([], "end_turn"), completion([], "max_tokens"),
                     completion([], "refusal"), {"content": [None]},
                     dict(completion([call("contract", {})]), usage=None),
                     completion([call("contract", {}, "same"), call("describe", {}, "same")])]
        for response in responses:
            with self.subTest(response=response), self.assertRaises(InvestigationFailed):
                asyncio.run(investigate(self.tools, ScriptedClient([response])))

    def test_round_limit_stops_unfinished_investigation(self):
        client = ScriptedClient([completion([call("query", {"sql": "SELECT %d AS value" % i})]) for i in range(8)])
        with self.assertRaisesRegex(InvestigationFailed, "round budget"):
            asyncio.run(investigate(self.tools, client))
        self.assertEqual(len(client.requests), 8)

    def test_tool_limit_stops_parallel_call_batch(self):
        client = ScriptedClient([completion([call("query", {"sql": "SELECT %d AS value" % n}, "tool-%d" % n)
                                            for n in range(25)])])
        with self.assertRaisesRegex(InvestigationFailed, "tool budget"):
            asyncio.run(investigate(self.tools, client))
        self.assertEqual(len(self.tools.trace), 24)

    def test_status_fields_are_validated_before_accepting_decision(self):
        self.tools.call("contract")
        evidence = self.tools.trace[0]["evidence_id"]
        decisions = [
            {"status": "candidate", "explanation": "Claim", "evidence_ids": [evidence]},
            {"status": "no_change", "explanation": "Claim", "evidence_ids": [evidence],
             "candidate_sql": "SELECT 1"},
            {"status": "needs_information", "explanation": "Claim", "evidence_ids": [evidence],
             "affected_ids": [], "required_fields": ["offset"]}]
        for decision in decisions:
            with self.subTest(decision=decision), self.assertRaises(InvestigationFailed):
                asyncio.run(investigate(self.tools, ScriptedClient([completion([call("finish", decision)])])))

    def test_model_evaluation_requires_explicit_configuration_before_creating_output(self):
        with patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(ValueError, "locally"):
            evaluate_all(self.root / "model-run", mode="anthropic")
        self.assertFalse((self.root / "model-run").exists())

    def test_repeated_calls_fail_and_preserve_failure_usage(self):
        client = ScriptedClient([completion([call("contract", {})])] * 4)
        with self.assertRaisesRegex(InvestigationFailed, "Repeated identical"):
            asyncio.run(investigate(self.tools, client))
        metadata = json.loads((self.tools.workspace / "model-run.json").read_text())
        self.assertEqual(metadata["status"], "failed")
        self.assertEqual(metadata["usage"]["input_tokens"], 80)


if __name__ == "__main__":
    unittest.main()
