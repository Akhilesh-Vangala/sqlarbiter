import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler
from http.server import HTTPServer
from pathlib import Path
from unittest.mock import patch

from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from sqlarbiter.platform.observability import Telemetry


class TraceExportTests(unittest.TestCase):
    def test_otlp_round_trip_and_parent_child_spans_without_source_payloads(self):
        received = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                payload = self.rfile.read(int(self.headers["Content-Length"]))
                message = ExportTraceServiceRequest()
                message.ParseFromString(payload)
                received.append(message)
                self.send_response(200)
                self.end_headers()

            def log_message(self, *args):
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with (
                tempfile.TemporaryDirectory() as directory,
                patch.dict(
                    os.environ,
                    {
                        "SQLARBITER_OTLP_ENDPOINT": "http://127.0.0.1:%d/v1/traces"
                        % server.server_port
                    },
                ),
            ):
                telemetry = Telemetry(directory)
                with telemetry.root("investigation"):
                    with telemetry.span("llm.round", **{"gen_ai.usage.input_tokens": 20}):
                        with telemetry.span("tool.query", **{"arbiter.engine": "duckdb"}):
                            pass
                telemetry.close()
                local = [
                    json.loads(line)
                    for line in (Path(directory) / "spans.jsonl").read_text().splitlines()
                ]
                self.assertEqual(
                    {span["name"] for span in local}, {"investigation", "llm.round", "tool.query"}
                )
                self.assertEqual(len({span["context"]["trace_id"] for span in local}), 1)
                self.assertEqual(local[0]["parent_id"], local[1]["context"]["span_id"])
                exported = [
                    span
                    for message in received
                    for resource in message.resource_spans
                    for scope in resource.scope_spans
                    for span in scope.spans
                ]
                self.assertEqual(len(exported), 3)
                self.assertFalse(
                    any(
                        "prompt" in a.key or "sql" in a.key
                        for span in exported
                        for a in span.attributes
                    )
                )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
