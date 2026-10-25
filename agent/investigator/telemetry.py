"""OpenTelemetry spans exported locally and optionally over OTLP/HTTP to Phoenix."""
import json
import os
import threading
from pathlib import Path

from opentelemetry import trace
from opentelemetry.propagate import extract
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export import SpanExporter
from opentelemetry.sdk.trace.export import SpanExportResult


class LocalExporter(SpanExporter):
    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.Lock()

    def export(self, spans):
        with self.lock, self.path.open("a") as output:
            for span in spans:
                output.write(json.dumps(json.loads(span.to_json())) + "\n")
        return SpanExportResult.SUCCESS

    def shutdown(self):
        pass


class Telemetry:
    def __init__(self, directory, service="sqlarbiter-investigator"):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        self.provider = TracerProvider(resource=Resource.create({"service.name": service}))
        self.provider.add_span_processor(SimpleSpanProcessor(LocalExporter(directory / "spans.jsonl")))
        endpoint = os.environ.get("SQLARBITER_OTLP_ENDPOINT")
        if endpoint:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
            self.provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, timeout=3)))
        self.tracer = self.provider.get_tracer("sqlarbiter", "0.2.0")

    def span(self, name, **attributes):
        attributes.setdefault("openinference.span.kind", "LLM" if name.startswith("llm.") else (
            "TOOL" if name.startswith("tool.") else "CHAIN"))
        return self.tracer.start_as_current_span(name, attributes=attributes)

    def root(self, name, **attributes):
        attributes.setdefault("openinference.span.kind", "CHAIN")
        context = extract({"traceparent": os.environ.get("SQLARBITER_TRACEPARENT", "")})
        return self.tracer.start_as_current_span(name, context=context, attributes=attributes)

    def close(self):
        self.provider.shutdown()


def current_traceparent():
    context = trace.get_current_span().get_span_context()
    if not context.is_valid:
        return ""
    return "00-%032x-%016x-%02x" % (context.trace_id, context.span_id, int(context.trace_flags))
