import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from vdir.jobs import Conflict, JobStore
from vdir.service import case_version, find_case, process_next


def request(case_id="case-001"):
    return {"kind": "investigation", "case_id": case_id, "investigator": "baseline",
            "input_version": case_version(find_case(case_id))}


class PersistentJobTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = JobStore(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_atomic_claim_has_one_owner_across_connections(self):
        job_id, _ = self.store.enqueue(request(), "atomic-claim")
        with ThreadPoolExecutor(max_workers=2) as pool:
            claims = list(pool.map(lambda _: JobStore(self.root).claim(), range(2)))
        self.assertEqual(sum(claim is not None for claim in claims), 1)
        self.assertEqual(next(claim for claim in claims if claim)["id"], job_id)

    def test_expired_lease_is_interrupted_without_automatic_retry(self):
        job_id, _ = self.store.enqueue(request(), "lease-expiry")
        stale = self.store.claim(lease_seconds=-1)
        self.assertIsNone(self.store.claim())
        self.assertEqual(self.store.get(job_id)["status"], "interrupted")
        with self.assertRaises(Conflict):
            self.store.finish(stale, result={})
        self.assertEqual(len(self.store.list()), 1)

    def test_heartbeat_extends_lease_only_for_current_owner(self):
        job_id, _ = self.store.enqueue(request(), "heartbeat-job")
        job = self.store.claim(lease_seconds=2)
        now = time.time()
        with patch("vdir.jobs.time.time", return_value=now + 1):
            self.store.heartbeat(job)
        with patch("vdir.jobs.time.time", return_value=now + 3):
            self.assertIsNone(self.store.claim())
            self.assertEqual(self.store.get(job_id)["status"], "running")
        with self.assertRaises(Conflict):
            self.store.heartbeat(dict(job, owner="someone-else"))

    def test_state_survives_reopening_and_code_change_fails_before_execution(self):
        payload = request()
        payload["input_version"] = "outdated"
        job_id, _ = self.store.enqueue(payload, "changed-source")
        process_next(JobStore(self.root))
        value = JobStore(self.root).get(job_id)
        self.assertEqual(value["status"], "failed")
        self.assertIsNone(value["result"])
        self.assertEqual([event["name"] for event in value["events"]], ["queued", "running", "failed"])

    def test_enqueue_is_atomic_under_duplicate_requests(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: JobStore(self.root).enqueue(request(), "same-request"), range(2)))
        self.assertEqual(results[0][0], results[1][0])
        self.assertEqual(sum(created for _, created in results), 1)

    def test_idempotency_conflicts_and_queue_limit(self):
        self.store.enqueue(request(), "same-key")
        with self.assertRaisesRegex(Conflict, "different request"):
            self.store.enqueue(request("case-002"), "same-key")
        for index in range(15):
            self.store.enqueue(request(), "queued-%d" % index)
        with self.assertRaisesRegex(Conflict, "Queue is full"):
            self.store.enqueue(request(), "overflow")


if __name__ == "__main__":
    unittest.main()
