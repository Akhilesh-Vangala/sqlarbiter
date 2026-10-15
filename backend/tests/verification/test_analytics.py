import json
import sys
import tempfile
import unittest
from pathlib import Path

from vdir.domain.cases import Incident
from vdir.domain.cases import Source
from vdir.evaluation.evaluation import export_workspace
from vdir.evaluation.evaluation import _matches

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "backend/agents/investigator"))
from tools import EvidenceTools


class AnalyticalGuards(unittest.TestCase):
    def test_row_cell_column_and_schema_budgets_on_both_engines(self):
        columns = tuple("col_%s INTEGER" % ("a" * (i + 1)) for i in range(60))
        source = Source("large", {
            "rows": (("row_id INTEGER", "value TEXT"), tuple((i, "x" * 1000) for i in range(150))),
            "wide": (columns, (tuple(range(60)),))})
        case = Incident("large", {}, (source,), "SELECT row_id FROM rows", {}, ())
        for engine in ("sqlite", "duckdb"):
            with self.subTest(engine=engine), tempfile.TemporaryDirectory() as directory:
                tools = EvidenceTools(export_workspace(case, Path(directory) / "case", engine))
                query = tools.call("query", {"sql": "SELECT row_id FROM rows ORDER BY row_id"})
                self.assertTrue(query["ok"])
                self.assertEqual(len(query["result"]["rows"]), 100)
                self.assertTrue(query["result"]["truncated"])
                self.assertFalse(_matches(query, {"output": ["row_id"]}, {}))
                cell = tools.call("query", {"sql": "SELECT value FROM rows LIMIT 1"})
                self.assertEqual(len(cell["result"]["rows"][0][0]), 256)
                self.assertTrue(cell["result"]["truncated"])
                self.assertFalse(tools.call("query", {"sql": "SELECT * FROM wide"})["ok"])
                first = tools.call("describe")["result"]
                self.assertEqual(len(first["columns"]), 50)
                self.assertEqual(first["next_cursor"], 50)
                self.assertEqual(len(tools.call("describe", {"cursor": 50})["result"]["columns"]), 12)
                profile = tools.call("profile", {"table": "rows", "columns": ["row_id"]})["result"]
                self.assertEqual(profile["row_count"], 150)
                self.assertEqual(profile["statistics"][0]["distinct_nonnull_values"], 150)

    def test_duckdb_denies_external_access_and_mutations(self):
        source = Source("test", {"events": (("event_id TEXT",), (("one",),))})
        case = Incident("test", {}, (source,), "SELECT * FROM events", {}, ())
        with tempfile.TemporaryDirectory() as directory:
            tools = EvidenceTools(export_workspace(case, Path(directory) / "case", "duckdb"))
            queries = ["SELECT * FROM read_csv('/etc/passwd')", "SELECT * FROM duckdb_settings()",
                "SELECT getenv('ANTHROPIC_API_KEY')", "SELECT current_setting('home_directory')",
                "COPY events TO '/tmp/exfiltrate.csv'", "INSTALL httpfs", "ATTACH '/tmp/secret' AS x",
                "SELECT * FROM events; DROP TABLE events", "SELECT repeat('x',100000000)"]
            for sql in queries:
                with self.subTest(sql=sql):
                    self.assertFalse(tools.call("query", {"sql": sql})["ok"])
            self.assertTrue(tools.call("query", {"sql": "SELECT event_id, ROW_NUMBER() OVER () AS n FROM events"})["ok"])
