"""Transport/SDK protocol checks, explicitly not model-quality evaluations."""
import asyncio
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx2
from anthropic import AsyncAnthropic

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend" / "investigator_runtime"))
from model import AnthropicClient, InvestigationFailed


def sse(name="contract", params=None):
    message = {"id": "msg-test", "type": "message", "role": "assistant", "model": "configured-model",
               "content": [], "stop_reason": None, "stop_sequence": None,
               "usage": {"input_tokens": 20, "output_tokens": 0}}
    events = [
        {"type": "message_start", "message": message},
        {"type": "content_block_start", "index": 0,
         "content_block": {"type": "tool_use", "id": "t1", "name": name, "input": {}}},
        {"type": "content_block_delta", "index": 0,
         "delta": {"type": "input_json_delta", "partial_json": json.dumps(params or {})}},
        {"type": "content_block_stop", "index": 0},
        {"type": "message_delta", "delta": {"stop_reason": "tool_use", "stop_sequence": None},
         "usage": {"output_tokens": 10}}, {"type": "message_stop"}]
    return "".join("event: %s\ndata: %s\n\n" % (event["type"], json.dumps(event)) for event in events)


class SDKTests(unittest.IsolatedAsyncioTestCase):
    async def make_client(self, handler, event_path=None, spend=None):
        sdk = AsyncAnthropic(api_key="test-only-secret", max_retries=1,
                             http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)),
                             _strict_response_validation=True)
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-only-secret",
                                    "VDIR_ANTHROPIC_MODEL": "configured-model"}):
            return AnthropicClient(sdk=sdk, event_path=event_path, spend=spend)

    async def test_spend_rejection_prevents_messages_request(self):
        from vdir.spending import SpendLedger
        from test_spending import PRICE
        paths = []
        async def handler(request):
            paths.append(request.url.path)
            if "/models/" in request.url.path:
                return httpx2.Response(200, json={"type": "model", "id": "configured-model", "created_at": "2026-01-01T00:00:00Z", "display_name": "Test", "lifecycle": "active"})
            return httpx2.Response(200, json={"input_tokens": 20})
        with tempfile.TemporaryDirectory() as directory:
            ledger = SpendLedger(Path(directory) / "spend.sqlite", PRICE, ".001", ".001")
            client = await self.make_client(handler, spend=ledger)
            try:
                with self.assertRaisesRegex(InvestigationFailed, "allowance exhausted"):
                    await client.complete([], [])
            finally:
                await client.close()
            self.assertNotIn("/v1/messages", paths)
            self.assertEqual(ledger.summary()["accounted_usd"], 0)

    async def test_spend_stream_timeout_retains_reservation_without_automatic_retry(self):
        from vdir.spending import SpendLedger
        from test_spending import PRICE
        generations = []
        async def handler(request):
            if "/models/" in request.url.path:
                return httpx2.Response(200, json={"type": "model", "id": "configured-model", "created_at": "2026-01-01T00:00:00Z", "display_name": "Test", "lifecycle": "active"})
            if request.url.path.endswith("count_tokens"):
                return httpx2.Response(200, json={"input_tokens": 20})
            generations.append(request)
            raise httpx2.ReadTimeout("secret-provider-message", request=request)
        with tempfile.TemporaryDirectory() as directory:
            ledger = SpendLedger(Path(directory) / "spend.sqlite", PRICE)
            client = await self.make_client(handler, spend=ledger)
            try:
                with self.assertRaises(InvestigationFailed) as caught:
                    await client.complete([], [])
                self.assertNotIn("secret-provider-message", str(caught.exception))
            finally:
                await client.close()
            self.assertEqual(len(generations), 1)
            self.assertEqual(ledger.summary()["states"]["unknown"]["requests"], 1)
            self.assertAlmostEqual(ledger.summary()["accounted_usd"], .02056)

    async def test_spend_success_reconciles_complete_stream_usage(self):
        from vdir.spending import SpendLedger
        from test_spending import PRICE
        async def handler(request):
            if "/models/" in request.url.path:
                return httpx2.Response(200, json={"type": "model", "id": "configured-model", "created_at": "2026-01-01T00:00:00Z", "display_name": "Test", "lifecycle": "active"})
            if request.url.path.endswith("count_tokens"):
                return httpx2.Response(200, json={"input_tokens": 20})
            return httpx2.Response(200, headers={"content-type": "text/event-stream"}, content=sse())
        with tempfile.TemporaryDirectory() as directory:
            ledger = SpendLedger(Path(directory) / "spend.sqlite", PRICE)
            client = await self.make_client(handler, spend=ledger)
            try:
                await client.complete([], [])
            finally:
                await client.close()
            self.assertEqual(ledger.summary()["states"]["settled"]["requests"], 1)
            self.assertAlmostEqual(ledger.summary()["accounted_usd"], .00014)

    async def test_real_sdk_assembles_stream_and_retries_rate_limit(self):
        requests = []
        failures = 0
        async def handler(request):
            nonlocal failures
            requests.append(request)
            if "/models/" in request.url.path:
                return httpx2.Response(200, json={"type": "model", "id": "configured-model",
                    "created_at": "2026-01-01T00:00:00Z", "display_name": "Test", "lifecycle": "active"})
            if request.url.path.endswith("count_tokens"):
                return httpx2.Response(200, json={"input_tokens": 20})
            if failures == 0:
                failures += 1
                return httpx2.Response(429, headers={"retry-after-ms": "1"},
                    json={"type": "error", "error": {"type": "rate_limit_error", "message": "limited"}})
            return httpx2.Response(200, headers={"content-type": "text/event-stream"}, content=sse())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            client = await self.make_client(handler, path)
            try:
                result = await client.complete([{ "role": "user", "content": "test"}], [])
            finally:
                await client.close()
            self.assertEqual(result["content"][0]["input"], {})
            self.assertEqual(result["usage"]["output_tokens"], 10)
            self.assertEqual(client.input_tokens, 20)
            self.assertEqual(len([r for r in requests if r.url.path == "/v1/messages"]), 2)
            self.assertTrue(json.loads(requests[-1].content)["stream"])
            self.assertNotIn("test-only-secret", path.read_text())
            self.assertEqual(json.loads(path.read_text().splitlines()[-1])["event"], "message_stop")

    async def test_authentication_error_is_sanitized(self):
        async def handler(request):
            return httpx2.Response(401, json={"type": "error", "error": {
                "type": "authentication_error", "message": "test-only-secret"}})
        client = await self.make_client(handler)
        try:
            with self.assertRaisesRegex(InvestigationFailed, "HTTP 401") as caught:
                await client.complete([], [])
            self.assertNotIn("test-only-secret", str(caught.exception))
        finally:
            await client.close()

    async def test_preflight_context_guard_prevents_generation(self):
        paths = []
        async def handler(request):
            paths.append(request.url.path)
            if "/models/" in request.url.path:
                return httpx2.Response(200, json={"type": "model", "id": "configured-model",
                    "created_at": "2026-01-01T00:00:00Z", "display_name": "Test", "lifecycle": "active"})
            return httpx2.Response(200, json={"input_tokens": 16001})
        client = await self.make_client(handler)
        try:
            with self.assertRaisesRegex(InvestigationFailed, "before generation"):
                await client.complete([], [])
            self.assertNotIn("/v1/messages", paths)
        finally:
            await client.close()

    async def test_langgraph_uses_real_sdk_streaming_with_mock_http_transport(self):
        from graph import investigate as graph_investigate
        from tools import EvidenceTools
        from vdir.cases import incidents
        from vdir.evaluation import export_workspace
        from telemetry import Telemetry
        rounds = 0
        async def handler(request):
            nonlocal rounds
            if "/models/" in request.url.path:
                return httpx2.Response(200, json={"type": "model", "id": "configured-model",
                    "created_at": "2026-01-01T00:00:00Z", "display_name": "Test", "lifecycle": "active"})
            if request.url.path.endswith("count_tokens"):
                self.assertIn("record_plan", json.loads(request.content)["system"])
                return httpx2.Response(200, json={"input_tokens": 20})
            rounds += 1
            if rounds == 1:
                stream = sse()
            else:
                messages = json.loads(request.content)["messages"]
                evidence = json.loads(messages[-1]["content"][0]["content"])["evidence_id"]
                stream = sse("finish", {"status": "no_change", "explanation": "Current contract satisfied.",
                                         "evidence_ids": [evidence]})
            return httpx2.Response(200, headers={"content-type": "text/event-stream"}, content=stream)
        with tempfile.TemporaryDirectory() as directory:
            workspace = export_workspace(incidents()[4], Path(directory) / "evidence")
            telemetry = Telemetry(workspace)
            tools = EvidenceTools(workspace, telemetry=telemetry)
            client = await self.make_client(handler)
            try:
                with telemetry.root("investigation"):
                    response = await graph_investigate(tools, client)
            finally:
                await client.close()
                telemetry.close()
            self.assertEqual(rounds, 2)
            self.assertEqual(response["model_run"]["usage"]["input_tokens"], 40)
            self.assertEqual(response["model_run"]["resolved_model"], "configured-model")
            self.assertIn('graph.model', (workspace / "spans.jsonl").read_text())
            self.assertIn('graph.precheck', (workspace / "spans.jsonl").read_text())
            self.assertEqual(response["agent_workflow"]["public_precheck"]["status"], "passed")
            for filename in ("model-run.json", "graph-receipts.sqlite", "graph-checkpoints.sqlite"):
                self.assertNotIn(b"test-only-secret", (workspace / filename).read_bytes())
