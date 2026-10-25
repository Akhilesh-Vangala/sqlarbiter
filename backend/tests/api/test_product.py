"""Product error recovery, signed evidence, streaming and hosted-account boundaries."""
import copy
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from uuid import uuid4

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sqlarbiter.product.accounts import Provider, attach as accounts
from sqlarbiter.uploads.api import attach as uploads
from sqlarbiter.uploads.ingestion import Preview, Upload, UploadProblem, preview, profile
from sqlarbiter.uploads.service import run
from sqlarbiter.uploads.signing import attest, verify_report

ROOT = Path(__file__).resolve().parents[3]
SOURCE = "id,amount,region,status\na,12.34,East,done\na,12.34,East,done\nb,2.50,West,pending\n"


def upload(source=SOURCE):
    return Upload(csv=source, mapping={"key": "c0", "amount": "c1", "group": "c2", "status": "c3"},
                  options={"eligible_status": "done", "unit": "dollars", "reported_total": "24.68"})


class ProductEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        uploads(self.app, "SQLArbiter", ROOT)
        self.client = TestClient(self.app)

    def test_profile_and_preview_find_late_error_without_exposing_every_record(self):
        source = "id,amount\n" + "".join(f"item-{i},1.00\n" for i in range(2600))
        inspected = profile(source)
        self.assertEqual(len(inspected["preview"]), 10)
        self.assertEqual(inspected["columns"][1]["numeric"], 2600)
        selected = preview(Preview(csv=source, rows=[2502]))
        self.assertEqual(selected["rows"][0]["row"], 2502)
        self.assertEqual(selected["rows"][0]["cells"][0], "item-2500")
        searched = preview(Preview(csv=source, search="item-2599"))
        self.assertEqual(searched["matches"], 1)
        self.assertLessEqual(len(preview(Preview(csv=source))["rows"]), 25)

    def test_structured_conflict_names_record_and_column_without_echoing_values(self):
        response = self.client.post("/api/uploads/analyze", json=upload("id,amount,region,status\nprivate-id,12,East,done\nprivate-id,13,East,done\n").model_dump())
        self.assertEqual(response.status_code, 422)
        value = response.json()
        self.assertEqual({issue["row"] for issue in value["issues"]}, {2, 3})
        self.assertNotIn("private-id", response.text)
        self.assertTrue(value["hint"])

    def test_invalid_amount_and_ragged_record_are_actionable(self):
        for source in ("id,amount,region,status\na,oops,East,done\n", "id,amount\na\n"):
            value = self.client.post("/api/uploads/analyze", json=upload(source).model_dump())
            self.assertEqual(value.status_code, 422)
            self.assertEqual(value.json()["issues"][0]["row"], 2)

    def test_duplicate_impact_has_record_locations_and_zero_false_causality(self):
        result = run(upload())
        self.assertEqual(result["data_quality"]["duplicates"][0]["row"], 3)
        self.assertEqual(result["data_quality"]["duplicate_impact_cents"], 1234)
        self.assertEqual(result["summary"]["excluded_source_rows"], 1)

    def test_attestation_rejects_nested_tampering_and_wrong_key(self):
        with patch.dict(os.environ, {"SQLARBITER_REPORT_SIGNING_KEY": "a"*64}):
            report = attest(run(upload()))
            self.assertTrue(verify_report(report))
            altered = copy.deepcopy(report)
            altered["results"][0]["total_cents"] = 99
            self.assertFalse(verify_report(altered))
            altered = copy.deepcopy(report)
            altered["checks"][next(iter(altered["checks"]))] = False
            self.assertFalse(verify_report(altered))
        with patch.dict(os.environ, {"SQLARBITER_REPORT_SIGNING_KEY": "b"*64}):
            self.assertFalse(verify_report(report))
        for receipt in (None, "bad", {}, {"version": "v1", "signature": "x"}):
            self.assertFalse(verify_report({"attestation": receipt}))
        with self.assertRaises(ValueError):
            attest({"checks": {"independent": False}})

    def test_sse_reports_real_stages_then_one_authenticated_result(self):
        response = self.client.post("/api/uploads/analyze-stream", json=upload().model_dump())
        self.assertIn("text/event-stream", response.headers["content-type"])
        events = []
        for block in response.text.strip().split("\n\n"):
            lines = block.splitlines()
            events.append((lines[0].removeprefix("event: "), json.loads(lines[1].removeprefix("data: "))))
        self.assertEqual([data["stage"] for kind, data in events if kind == "stage" and data["state"] == "complete"],
                         ["source", "contract", "reference", "sql", "reconcile", "report"])
        self.assertEqual(sum(kind == "result" for kind, _ in events), 1)
        self.assertEqual(events[-1][0], "result")
        self.assertTrue(verify_report(events[-1][1]))

    def test_sse_failure_has_no_verified_result(self):
        response = self.client.post("/api/uploads/analyze-stream", json=upload("id,amount,region,status\na,wrong,East,done\n").model_dump())
        self.assertIn("event: problem", response.text)
        self.assertNotIn("event: result", response.text)


class HostedAccountTests(unittest.TestCase):
    def setUp(self):
        self.owner = str(uuid4())
        self.calls, self.rows = [], []
        self.status = 200
        self.service = Provider("https://account.example", "sb_publishable_" + "x"*32, httpx.MockTransport(self.respond))
        app = FastAPI()
        uploads(app, "SQLArbiter", ROOT)
        accounts(app, self.service)
        self.client = TestClient(app, base_url="https://verify.example")

    def respond(self, request):
        self.calls.append(request)
        if self.status != 200:
            return httpx.Response(self.status, text="private-provider-diagnostics-and-token")
        path = request.url.path
        if path.endswith("/token"):
            return httpx.Response(200, json={"access_token": "access-private", "refresh_token": "refresh-private", "expires_in": 3600})
        if path.endswith("/user"):
            self.assertEqual(request.headers.get("authorization"), "Bearer access-private")
            return httpx.Response(200, json={"id": self.owner, "email": "person@example.com"})
        if path.startswith("/rest/"):
            self.assertEqual(request.headers["authorization"], "Bearer access-private")
            if request.method == "POST":
                self.rows.append(json.loads(request.content))
                return httpx.Response(201, json=[self.rows[-1]])
            if request.method == "GET":
                self.assertEqual(request.url.params.get("owner_id"), "eq." + self.owner)
                found = [r for r in self.rows if request.url.params.get("id", "eq."+r["id"]) == "eq."+r["id"]]
                return httpx.Response(200, json=found)
        return httpx.Response(204)

    def sign_in(self):
        return self.client.post("/api/account/sign-in", json={"email": "person@example.com", "password": "a-private-password"})

    def test_session_is_verified_and_tokens_are_only_secure_httponly_cookies(self):
        result = self.sign_in()
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["id"], self.owner)
        self.assertNotIn("private", result.text)
        cookies = result.headers.get_list("set-cookie")
        self.assertEqual(len(cookies), 2)
        self.assertTrue(all("HttpOnly" in c and "Secure" in c and "SameSite=strict" in c and "__Host-" in c for c in cookies))
        self.assertEqual(self.client.get("/api/account/me").json()["id"], self.owner)
        self.assertEqual(self.client.post("/api/account/refresh", json={}).status_code, 200)

    def test_unauthenticated_history_is_not_shared_or_anonymous(self):
        self.assertEqual(self.client.get("/api/account/investigations").status_code, 401)
        self.assertEqual(self.rows, [])

    def test_server_recomputes_report_and_report_only_save_has_no_source_samples(self):
        self.sign_in()
        value = {"id": str(uuid4()), "title": "Revenue", "filename": "own.csv", "status": "completed", "upload": upload().model_dump(), "consent": True, "retain_source": False}
        self.assertEqual(self.client.post("/api/account/investigations", json=value).status_code, 200)
        row = self.rows[0]
        self.assertEqual(row["owner_id"], self.owner)
        self.assertIsNone(row["source"])
        self.assertEqual(row["profile"]["preview"], [])
        self.assertTrue(all("samples" not in c for c in row["profile"]["columns"]))
        self.assertTrue(verify_report(row["report"]))
        self.assertEqual(row["report"]["summary"]["verified_total_cents"], 1234)
        self.assertEqual(self.client.get("/api/account/investigations/"+row["id"]).json()["upload"]["csv"], "")
        value["id"] = str(uuid4())
        value["retain_source"] = True
        self.client.post("/api/account/investigations", json=value)
        self.assertEqual(self.rows[-1]["source"], SOURCE)

    def test_no_consent_or_spoofed_owner_or_client_report_can_be_saved(self):
        self.sign_in()
        value = {"id": str(uuid4()), "title": "Revenue", "filename": "own.csv", "status": "completed", "upload": upload().model_dump(), "consent": False}
        self.assertEqual(self.client.post("/api/account/investigations", json=value).status_code, 422)
        value.update(consent=True, owner_id=str(uuid4()), report={"passed": True})
        self.assertEqual(self.client.post("/api/account/investigations", json=value).status_code, 422)
        self.assertEqual(self.rows, [])

    def test_foreign_project_and_unowned_detail_are_unavailable(self):
        self.sign_in()
        self.assertEqual(self.client.get("/api/account/investigations/"+str(uuid4())).status_code, 404)
        value = {"id": str(uuid4()), "title": "Revenue", "filename": "own.csv", "project_id": str(uuid4()), "status": "draft", "upload": upload().model_dump(), "consent": True}
        self.assertEqual(self.client.post("/api/account/investigations", json=value).status_code, 404)
        self.assertFalse(self.rows)

    def test_provider_failure_and_validation_do_not_echo_credentials(self):
        for status, expected in ((429, 429), (500, 503), (400, 400)):
            self.status = status
            response = self.sign_in()
            self.assertEqual(response.status_code, expected)
            self.assertNotIn("private", response.text)
        response = self.client.post("/api/account/sign-in", json={"email": "bad", "password": {"secret": "must-not-reflect"}})
        self.assertEqual(response.status_code, 422)
        self.assertNotIn("must-not-reflect", response.text)

    def test_logout_clears_cookies_even_when_provider_unavailable(self):
        self.sign_in()
        self.status = 500
        result = self.client.post("/api/account/sign-out", json={})
        self.assertEqual(result.json(), {"signed_out": True, "provider_revoked": False})
        self.assertTrue(all("Max-Age=0" in c for c in result.headers.get_list("set-cookie")))

    def test_admin_keys_and_non_origin_provider_urls_are_refused(self):
        with self.assertRaises(ValueError):
            Provider("https://account.example", "sb_secret_admin")
        with self.assertRaises(ValueError):
            Provider("https://account.example/redirect", "sb_publishable_"+"x"*32)
        with patch.dict(os.environ, {"SQLARBITER_ACCOUNT_SIGNUP": "0"}):
            self.assertFalse(self.client.get("/api/account/config").json()["signup_enabled"])
            self.assertEqual(self.client.post("/api/account/sign-up", json={}).status_code, 403)

    def test_missing_configuration_is_explicitly_disabled(self):
        app = FastAPI()
        with patch.dict(os.environ, {"SQLARBITER_SUPABASE_URL": "", "SQLARBITER_SUPABASE_PUBLISHABLE_KEY": ""}):
            accounts(app)
        with TestClient(app) as client:
            self.assertFalse(client.get("/api/account/config").json()["enabled"])
            self.assertEqual(client.post("/api/account/sign-in", json={}).status_code, 503)
