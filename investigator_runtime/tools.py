"""Allowlisted evidence tools; exported runtime has no evaluator imports.

Not an OS sandbox: arbitrary Python would still have the host user's authority.
Only these tool operations should ever be exposed to a model.
"""
import hashlib
import json
from contextlib import nullcontext
from engines import execute, QueryRejected
from pathlib import Path


class ToolRejected(ValueError):
    pass


class EvidenceTools:
    def __init__(self, workspace, max_calls=24, telemetry=None):
        self.workspace = Path(workspace).resolve()
        self.manifest = self._read("incident.json")
        self.schema = self._read("schema.json")
        self.trace = []
        self.max_calls = max_calls
        self.telemetry = telemetry
        self.engine = self.manifest.get("engine", "sqlite")

    def _read(self, name):
        path = self.workspace / name
        if path.is_symlink() or path.resolve().parent != self.workspace:
            raise ToolRejected("Invalid evidence path")
        return json.loads(path.read_text())

    def call(self, method, params=None):
        context = self.telemetry.span("tool." + str(method), **{"vdir.engine": self.engine}) if self.telemetry else nullcontext()
        with context:
            return self._call(method, params)

    def _call(self, method, params=None):
        if len(self.trace) >= self.max_calls:
            raise ToolRejected("Tool-call budget exceeded")
        params = {} if params is None else params
        record = {"method": method, "params": params, "sequence": len(self.trace) + 1}
        try:
            if not isinstance(method, str):
                raise ToolRejected("Tool method must be a string")
            if not isinstance(params, dict):
                raise ToolRejected("Tool parameters must be an object")
            if method == "query" and set(params) == {"sql"}:
                result = self.query(params["sql"])
            elif method == "describe" and set(params).issubset({"cursor"}):
                result = self.describe(params.get("cursor", 0))
            elif method == "profile" and set(params) == {"table", "columns"}:
                result = self.profile(params["table"], params["columns"])
            elif method in ("contract", "lineage", "changes", "current_sql") and not params:
                result = self.manifest[method]
            else:
                raise ToolRejected("Unknown tool or invalid parameters")
            record.update(ok=True, result=result)
            if len(json.dumps(result).encode()) > 32768:
                raise ToolRejected("Tool result exceeds 32768-byte context budget; narrow the request")
        except (ToolRejected, QueryRejected) as error:
            record.update(ok=False, error=str(error))
        identity = hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest()[:16]
        record["evidence_id"] = "ev-" + identity
        self.trace.append(record)
        return record

    def describe(self, cursor=0):
        if type(cursor) is not int or cursor < 0:
            raise ToolRejected("Schema cursor must be a nonnegative integer")
        columns = [{"table": table, "definition": definition}
                   for table, schema in self.schema.items() for definition in schema["definitions"]]
        return {"engine": self.engine, "total_columns": len(columns),
                "columns": columns[cursor:cursor + 50],
                "next_cursor": cursor + 50 if cursor + 50 < len(columns) else None}

    def profile(self, table, columns):
        if (not isinstance(table, str) or table not in self.schema
                or not isinstance(columns, list) or not 1 <= len(columns) <= 8
                or any(not isinstance(col, str) or col not in self.schema[table]["columns"] for col in columns)):
            raise ToolRejected("Profile requires one declared table and 1–8 declared columns")
        parts = ['COUNT(*) AS row_count']
        for index, column in enumerate(columns):
            parts.extend(['COUNT("%s") AS nonnull_%d' % (column, index),
                          'COUNT(DISTINCT "%s") AS distinct_%d' % (column, index)])
        result = self.query('SELECT ' + ', '.join(parts) + ' FROM "' + table + '"')
        row = result["rows"][0]
        count = row[0]
        return {"table": table, "row_count": count, "statistics": [
            {"column": col, "null_fraction": (count - row[1+2*i]) / count if count else None,
             "distinct_nonnull_values": row[2+2*i]} for i, col in enumerate(columns)],
            "scope": "exact aggregate on exported source snapshot; execution budget applies"}

    def query(self, sql):
        path = self.workspace / ("source.duckdb" if self.engine == "duckdb" else "source.sqlite")
        if path.is_symlink() or path.resolve().parent != self.workspace:
            raise ToolRejected("Invalid database path")
        result = execute(path, self.engine, self.schema, sql)
        result["snapshot_id"] = self.manifest["snapshot_id"]
        return result
