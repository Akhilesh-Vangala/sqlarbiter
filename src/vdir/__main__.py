"""Run a reproducible local comparison or evaluate a candidate SQL file."""
import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .environment import snapshots
from .verifier import verify_suite

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def main():
    from .config import load_local_configuration
    load_local_configuration()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, help="Evaluate this SELECT against all development cases")
    parser.add_argument("--investigate", type=Path, help="Investigate into a new output directory")
    parser.add_argument("--investigator", choices=("baseline", "anthropic"), default="baseline")
    parser.add_argument("--engine", choices=("sqlite", "duckdb"), default="duckdb")
    args = parser.parse_args()
    if args.investigate:
        if args.candidate:
            parser.error("Choose --candidate or --investigate")
        from .evaluation import evaluate_all
        try:
            report = evaluate_all(args.investigate, mode=args.investigator, engine=args.engine)
        except ValueError as error:
            parser.error(str(error))
        print(json.dumps(report, indent=2))
        if not report["passed"]:
            raise SystemExit(1)
        return
    if args.investigator != "baseline":
        parser.error("--investigator requires --investigate")
    if args.candidate:
        candidates = {args.candidate.name: args.candidate.read_text()}
    else:
        candidates = {path.stem: path.read_text()
                      for path in sorted((PROJECT_ROOT / "data" / "development" / "sql").glob("*.sql"))}
    results = {}
    for name, sql in candidates.items():
        results[name] = [asdict(check) for check in verify_suite(snapshots(), sql)]
    print(json.dumps({"scope": "development fixtures; no AI or broad benchmark",
                      "results": results}, indent=2))
    if args.candidate and not all(check["passed"] for check in results[args.candidate.name]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
