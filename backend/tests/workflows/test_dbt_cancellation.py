import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from sqlarbiter.workflows.dbt_workflow import run_dbt
from sqlarbiter.evaluation.evaluation import ExecutionInterrupted
from sqlarbiter.evaluation.evaluation import execution_scope


@unittest.skipUnless(os.name == "posix", "Process-group dbt execution uses POSIX supervision")
class DbtCancellationTests(unittest.TestCase):
    def test_interrupted_dbt_subprocess_is_terminated_and_reaped(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tool = root / "test-dbt"
            tool.write_text(
                "#!"
                + str(Path(sys.executable).resolve())
                + "\nimport os,time\nfrom pathlib import Path\nPath('dbt.pid').write_text(str(os.getpid()))\ntime.sleep(60)\n"
            )
            tool.chmod(0o700)
            stopped = threading.Event()
            errors = []

            def control():
                if stopped.is_set():
                    raise ExecutionInterrupted("Test cancellation")

            def execute():
                try:
                    with execution_scope(control):
                        run_dbt(root, root / "unused.duckdb", "test", [["build"]], tool)
                except BaseException as error:
                    errors.append(error)

            worker = threading.Thread(target=execute)
            worker.start()
            try:
                deadline = time.monotonic() + 5
                while not (root / "dbt.pid").exists() and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertTrue((root / "dbt.pid").exists(), errors)
            finally:
                stopped.set()
                worker.join(timeout=5)
            self.assertFalse(worker.is_alive())
            self.assertEqual(len(errors), 1)
            self.assertIsInstance(errors[0], ExecutionInterrupted)
            with self.assertRaises(ProcessLookupError):
                os.kill(int((root / "dbt.pid").read_text()), 0)
