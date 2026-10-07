"""Start the local web app and a separate persistent queue worker."""
import argparse
import os
import signal
import subprocess
import sys
from pathlib import Path


def main():
    from .config import load_local_configuration
    load_local_configuration()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--state-dir", type=Path, default=Path("artifacts/generated/app"))
    parser.add_argument("--no-worker", action="store_true")
    args = parser.parse_args()
    os.environ["VDIR_STATE_DIR"] = str(args.state_dir.resolve())
    from .api import create_app
    import uvicorn
    app = create_app()
    def terminate(signum, frame):
        # Uvicorn replays captured signals after closing the HTTP server. Turn
        # SIGTERM into an exception so our finally block always reaps the child.
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, terminate)
    worker = None
    if not args.no_worker:
        worker = subprocess.Popen([sys.executable, "-m", "vdir.worker", "--state-dir", str(args.state_dir.resolve())])
        print("Queue worker started [%d]" % worker.pid, flush=True)
    try:
        uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="info")
    finally:
        if worker:
            worker.terminate()
            try:
                worker.wait(timeout=10)
            except subprocess.TimeoutExpired:
                worker.kill()
                worker.wait()


if __name__ == "__main__":
    main()
