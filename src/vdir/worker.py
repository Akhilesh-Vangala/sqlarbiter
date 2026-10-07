"""Run the persistent job worker separately from the web server."""
import argparse
import os
import signal
import threading
from pathlib import Path

from .jobs import JobStore
from .service import process_next


def main():
    from .config import load_local_configuration
    load_local_configuration()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, default=Path(os.environ.get(
        "VDIR_STATE_DIR", "artifacts/generated/app")))
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    store = JobStore(args.state_dir)
    if args.once:
        process_next(store)
        return
    stopped = threading.Event()
    for number in (signal.SIGINT, signal.SIGTERM):
        signal.signal(number, lambda *_: stopped.set())
    while not stopped.is_set():
        if not process_next(store):
            stopped.wait(0.5)


if __name__ == "__main__":
    main()
