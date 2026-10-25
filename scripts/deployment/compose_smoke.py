"""Execute inside the API container against its real API and separate worker."""
import json
import os
import sys
import time
import urllib.request
import uuid

assert sys.version_info[:2] == (3, 11)
base = "http://127.0.0.1:8000"
token = os.environ["SQLARBITER_ACCESS_TOKEN"]

def request(path, payload=None, key=None):
    headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}
    if key:
        headers["Idempotency-Key"] = key
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(base + path, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.load(response)

assert request("/healthz")["status"] == "ok"
checks = []
for case in request("/api/incidents"):
    job = request("/api/jobs", {"case_id": case["id"], "investigator": "baseline"}, uuid.uuid4().hex)
    for _ in range(100):
        job = request("/api/jobs/" + job["id"])
        if job["status"] in ("completed", "failed", "interrupted"):
            break
        time.sleep(0.2)
    assert job["status"] == "completed", (case["id"], job["status"])
    assert job["result"]["grading"]["passed"], case["id"]
    assert job["result"]["engine"] == "duckdb"
    assert request("/api/jobs/" + job["id"] + "/report")["result_version"] == job["result_version"]
    if job["result"]["response"]["decision"]["status"] == "candidate":
        request("/api/jobs/" + job["id"] + "/review", {"version": job["result_version"], "action": "approved"})
    checks.append({"case_id": case["id"], "job_id": job["id"], "passed": True})
print(json.dumps({"python": sys.version.split()[0], "engine": "duckdb", "checks": checks}, indent=2))
