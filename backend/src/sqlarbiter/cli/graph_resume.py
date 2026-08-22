"""Explicit continuation for standalone exported graph runs, outside the app job queue."""

import argparse
import json
from pathlib import Path

from sqlarbiter.platform.config import load_local_configuration
from sqlarbiter.evaluation.evaluation import run_worker


def main():
    load_local_configuration()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument(
        "--guidance-file", type=Path, help="UTF-8 investigation guidance, at most 2000 characters"
    )
    action.add_argument(
        "--recover",
        action="store_true",
        help="Explicit recovery after interruption; unresolved calls remain blocked",
    )
    args = parser.parse_args()
    if args.guidance_file:
        if args.guidance_file.stat().st_size > 8000:
            parser.error("Guidance file exceeds size limit")
        guidance = args.guidance_file.read_text()
        if not guidance.strip() or len(guidance) > 2000:
            parser.error("Provide 1–2000 characters of guidance")
        continuation = {"guidance": guidance}
    else:
        continuation = {"recover": True}
    response = run_worker(args.workspace, mode="langgraph", continuation=continuation)
    print(json.dumps(response, indent=2))


if __name__ == "__main__":
    main()
