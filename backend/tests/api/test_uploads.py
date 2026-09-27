"""Actual user-input regression cases; no scripted model responses."""

import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlarbiter.uploads.api import attach
from sqlarbiter.uploads.ingestion import Upload, parse, safe_csv
from sqlarbiter.uploads.service import run


class CustomerUploadTests(unittest.TestCase):
    def upload(self, csv=None, **options):
        return Upload(
            csv=csv
            or "id,amount,region,status\na,10.01,East,done\na,10.01,East,done\nb,7.25,West,done\nc,9.00,West,pending\n",
            mapping={"key": "c0", "amount": "c1", "group": "c2", "status": "c3"},
            options={"unit": "dollars", "eligible_status": "done", **options},
        )

    def test_exact_cents_deduplication_and_status_filter(self):
        result = run(self.upload(reported_total="27.27"))
        self.assertEqual(result["summary"]["verified_total_cents"], 1726)
        self.assertEqual(result["summary"]["difference_cents"], -1001)
        self.assertEqual(result["summary"]["duplicate_deliveries"], 1)
        self.assertTrue(all(result["checks"].values()))
        self.assertEqual([r["total_cents"] for r in result["results"]], [1001, 725])

    def test_customer_value_changes_result(self):
        result = run(self.upload("id,amount,region,status\nx,3.33,North,done\n"))
        self.assertEqual(result["summary"]["verified_total_cents"], 333)

    def test_conflicting_logical_key_is_not_silently_repaired(self):
        with self.assertRaisesRegex(ValueError, "Conflicting"):
            run(self.upload("id,amount,region,status\nx,3.33,North,done\nx,4.00,North,done\n"))

    def test_no_eligibility_data_means_zero_not_an_invented_value(self):
        result = run(self.upload("id,amount,region,status\nx,3.33,North,pending\n"))
        self.assertEqual(result["results"], [])
        self.assertEqual(result["summary"]["verified_total_cents"], 0)

    def test_malformed_precision_and_mapping_are_rejected(self):
        for source in (
            "id,amount,region,status\nx,1.001,X,done\n",
            "id,amount,region,status\nx,NaN,X,done\n",
        ):
            with self.assertRaises(ValueError):
                run(self.upload(source))
        with self.assertRaises(ValueError):
            run(
                Upload(
                    csv="x,y\na,1\n", mapping={"key": "c0", "amount": "c1);DROP TABLE records;--"}
                )
            )

    def test_file_boundaries_and_formula_neutralization(self):
        for source in ("x,X\n1,2\n", "x,y\n1\n", "x\n\x00\n", "x\n" + "v\n" * 5001):
            with self.assertRaises(ValueError):
                parse(source)
        self.assertIn("'=HYPERLINK", safe_csv(["name", "n"], [["=HYPERLINK(1)", -2]]))
        self.assertIn(",-2", safe_csv(["name", "n"], [["safe", -2]]))

    def test_real_api_profile_analysis_and_stream_limit(self):
        app = FastAPI()
        attach(app, Path(__file__).resolve().parents[3])
        with TestClient(app) as client:
            payload = self.upload().model_dump()
            self.assertEqual(
                client.post("/api/uploads/profile", json={"csv": payload["csv"]}).json()["rows"], 4
            )
            response = client.post("/api/uploads/analyze", json=payload)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["summary"]["verified_total_cents"], 1726)
            too_large = client.post(
                "/api/uploads/profile",
                content=iter([b"x" * 600000, b"x" * 600000]),
                headers={"content-type": "application/json"},
            )
            self.assertEqual(too_large.status_code, 413)
            self.assertEqual(
                client.post(
                    "/api/uploads/profile", content="a,b", headers={"content-type": "text/csv"}
                ).status_code,
                415,
            )
            self.assertEqual(client.get("/uploads").status_code, 200)
