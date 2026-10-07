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

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "investigator_runtime"))
from model import AnthropicClient, InvestigationFailed


def sse():
    message = {"id": "msg-test", "type": "message", "role": "assistant", "model": "configured-model",
               "content": [], "stop_reason": None, "stop_sequence": None,
               "usage": {"input_tokens": 20, "output_tokens": 0}}
    events = [
        {"type": "message_start", "message": message},
        {"type": "content_block_start", "index": 0,
         "content_block": {"type": "tool_use", "id": "t1", "name": "contract", "input": {}}},
        {"type": "content_block_delta", "index": 0,
         "delta": {"type": "input_json_delta", "partial_json": "{}"}},
        {"type": "content_block_stop", "index": 0},
        {"type": "message_delta", "delta": {"stop_reason": "tool_use", "stop_sequence": None},
         "usage": {"output_tokens": 10}}, {"type": "message_stop"}]
    return "".join("event: %s\ndata: %s\n\n" % (event["type"], json.dumps(event)) for event in events)


class SDKTests(unittest.IsolatedAsyncioTestCase):
    async def make_client(self, handler, event_path=None):
        sdk = AsyncAnthropic(api_key="test-only-secret", max_retries=1,
                             http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)),
                             _strict_response_validation=True)
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-only-secret",
                                    "VDIR_ANTHROPIC_MODEL": "configured-model"}):
            return AnthropicClient(sdk=sdk, event_path=event_path)

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
