"""Runs from an exported runtime without importing the sqlarbiter evaluator package."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Explicit runtime directory only; launch with -I and a stripped environment.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from baseline import investigate
from tools import EvidenceTools
from tools import ToolRejected


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument(
        "--mode", choices=("baseline", "anthropic", "langgraph", "rpc"), default="baseline"
    )
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    from telemetry import Telemetry

    telemetry = Telemetry(args.workspace) if args.mode != "rpc" else None
    tools = EvidenceTools(args.workspace, telemetry=telemetry)
    if args.mode == "baseline":
        try:
            with telemetry.root(
                "investigation", **{"arbiter.mode": args.mode, "arbiter.engine": tools.engine}
            ):
                decision = investigate(tools)
            print(json.dumps({"decision": decision, "trace": tools.trace}))
        except (ValueError, ToolRejected) as error:
            print(json.dumps({"error": str(error), "trace": tools.trace}))
            raise SystemExit(1)
    elif args.mode in ("anthropic", "langgraph"):
        from model import AnthropicClient
        from model import InvestigationFailed
        from model import investigate as model_investigate

        if args.mode == "langgraph":
            from graph import investigate as model_investigate
        try:
            continuation = json.loads(sys.stdin.read()) if args.resume else {}
            if continuation and (
                args.mode != "langgraph" or set(continuation) - {"guidance", "recover"}
            ):
                raise InvestigationFailed("Invalid graph continuation")

            async def run():
                client = AnthropicClient(
                    telemetry=telemetry, event_path=args.workspace / "stream-events.jsonl"
                )
                try:
                    async with asyncio.timeout(240):
                        return await model_investigate(tools, client, **continuation)
                finally:
                    await client.close()

            with telemetry.root(
                "investigation", **{"arbiter.mode": args.mode, "arbiter.engine": tools.engine}
            ):
                response = asyncio.run(run())
            print(json.dumps(response))
        except Exception as error:
            metadata = args.workspace / "model-run.json"
            safe_error = (
                str(error)
                if isinstance(error, (InvestigationFailed, ToolRejected))
                else "Model protocol or execution failure"
            )
            print(
                json.dumps(
                    {
                        "decision": {},
                        "error": safe_error,
                        "trace": tools.trace,
                        "model_run": json.loads(metadata.read_text())
                        if metadata.exists()
                        else {"status": "failed"},
                    }
                )
            )
            telemetry.close()
            raise SystemExit(1)
    else:
        for line in sys.stdin:
            try:
                if len(line) > 60000:
                    raise ValueError("Request too large")
                request = json.loads(line)
                if not isinstance(request, dict) or set(request) - {"method", "params"}:
                    raise ValueError("Invalid request")
                result = tools.call(request.get("method"), request.get("params"))
            except (ValueError, ToolRejected) as error:
                result = {"ok": False, "error": str(error)}
            print(json.dumps(result), flush=True)

    if telemetry:
        telemetry.close()


if __name__ == "__main__":
    main()
