"""Run the persistent job worker separately from the web server."""
import argparse
import os
import signal
import threading
from pathlib import Path

from sqlarbiter.persistence.postgres_jobs import create_job_store
from sqlarbiter.workflows.service import process_next


def main():
    from sqlarbiter.platform.config import load_local_configuration
    load_local_configuration()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, default=Path(os.environ.get(
        "SQLARBITER_STATE_DIR", "artifacts/generated/app")))
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    store = create_job_store(args.state_dir)
    try:
        if args.once:
            process_next(store)
            return
        stopped = threading.Event()
        for number in (signal.SIGINT, signal.SIGTERM):
            signal.signal(number, lambda *_: stopped.set())
        while not stopped.is_set():
            if not process_next(store, stopped):
                stopped.wait(0.5)
    finally:
        close = getattr(store, "close", None)
        if close:
            close()


if __name__ == "__main__":
    main()
