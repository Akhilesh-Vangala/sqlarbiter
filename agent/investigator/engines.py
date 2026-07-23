"""Read-only analytical backends with an intentionally restricted SQL surface."""

import sqlite3
import threading
from datetime import date
from datetime import datetime
from decimal import Decimal

import sqlglot
from sqlglot import exp


class QueryRejected(ValueError):
    pass


def select_sql(sql, engine, tables):
    if not isinstance(sql, str) or not sql.strip() or len(sql) > 50000:
        raise QueryRejected("SQL must be a nonempty string of at most 50000 characters")
    try:
        expressions = sqlglot.parse(sql, read=engine)
    except sqlglot.errors.ParseError:
        raise QueryRejected("Invalid SQL syntax") from None
    if len(expressions) != 1 or not isinstance(expressions[0], (exp.Select, exp.Union)):
        raise QueryRejected("Only a single SELECT query is permitted")
    tree = expressions[0]
    allowed_ctes = {cte.alias for cte in tree.find_all(exp.CTE)}
    for table in tree.find_all(exp.Table):
        if (
            not isinstance(table.this, exp.Identifier)
            or table.db
            or table.catalog
            or table.name not in set(tables) | allowed_ctes
        ):
            raise QueryRejected("Only declared source tables and CTEs are permitted")
    forbidden = (
        exp.Insert,
        exp.Update,
        exp.Delete,
        exp.Create,
        exp.Drop,
        exp.Command,
        exp.Copy,
        exp.Into,
        exp.Attach,
        exp.Pragma,
        exp.Lock,
        exp.Set,
    )
    if any(isinstance(node, forbidden) for node in tree.walk()):
        raise QueryRejected("SQL contains a prohibited operation")
    allowed = {
        "SUM",
        "COUNT",
        "MAX",
        "MIN",
        "ABS",
        "COALESCE",
        "SUBSTRING",
        "DATE",
        "PRINTF",
        "CAST",
        "TRY_CAST",
        "ROW_NUMBER",
        "RANK",
        "DENSE_RANK",
        "AVG",
        "ROUND",
        "NULLIF",
        "UPPER",
        "LOWER",
        "LENGTH",
        "DATE_TRUNC",
        "TS_OR_DS_TO_DATE",
        "TIME_TO_STR",
        "STR_TO_TIME",
        "EXTRACT",
        "CURRENT_DATE",
        "IF",
        "AND",
        "OR",
        "CASE",
        "EXISTS",
    }
    for func in tree.find_all(exp.Func):
        name = func.name.upper() if isinstance(func, exp.Anonymous) else func.sql_name()
        if name not in allowed:
            raise QueryRejected("SQL function is outside the analytical allowlist: " + name)
    return sql.strip().rstrip(";")


def normalize(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else str(value)
    if isinstance(value, bytes):
        raise QueryRejected("Binary query results are not supported")
    return value


def execute(path, engine, schema, sql, limit=100):
    sql = select_sql(sql, engine, schema)
    # Outer LIMIT preserves inner GROUP BY/window/UNION semantics; fetch one extra
    # row solely to report truncation. It does not bound scan/aggregation work.
    bounded = "SELECT * FROM (%s) AS sqlarbiter_bounded LIMIT %d" % (sql, limit + 1)
    if engine == "duckdb":
        import duckdb

        conn = duckdb.connect(
            str(path),
            read_only=True,
            config={
                "threads": 1,
                "memory_limit": "128MB",
                "enable_external_access": False,
                "autoload_known_extensions": False,
                "autoinstall_known_extensions": False,
                "allow_unsigned_extensions": False,
                "lock_configuration": True,
            },
        )
        timer = threading.Timer(3, conn.interrupt)
        timer.start()
        try:
            cursor = conn.execute(bounded)
            columns = [column[0] for column in cursor.description]
            rows = cursor.fetchmany(limit + 1)
        except duckdb.Error:
            raise QueryRejected("DuckDB query rejected or execution budget exceeded") from None
        finally:
            timer.cancel()
            timer.join()
            conn.close()
    elif engine == "sqlite":
        cte_names = {cte.alias for cte in sqlglot.parse_one(sql, read="sqlite").find_all(exp.CTE)}
        conn = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
        try:

            def modifier(*args):
                if (
                    len(args) != 2
                    or args[0] != "%+d minutes"
                    or type(args[1]) is not int
                    or not -840 <= args[1] <= 720
                ):
                    raise QueryRejected("Unsupported date modifier")
                return "%+d minutes" % args[1]

            conn.create_function("printf", -1, modifier)
            conn.execute("PRAGMA query_only=ON")

            def authorize(action, first, second, database, trigger):
                if action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_RECURSIVE):
                    return sqlite3.SQLITE_OK
                # SQLite emits a database-less, empty-column read for optimized
                # COUNT(*) over a declared source table inside nested CTEs.
                if action == sqlite3.SQLITE_READ and (
                    (first in schema and database == "main")
                    or (first in set(schema) | cte_names and database is None and second == "")
                ):
                    return sqlite3.SQLITE_OK
                if action == sqlite3.SQLITE_FUNCTION and second in {
                    "sum",
                    "count",
                    "max",
                    "min",
                    "abs",
                    "coalesce",
                    "substr",
                    "date",
                    "printf",
                    "row_number",
                    "rank",
                    "dense_rank",
                    "avg",
                    "round",
                    "nullif",
                    "upper",
                    "lower",
                    "length",
                }:
                    return sqlite3.SQLITE_OK
                return sqlite3.SQLITE_DENY

            conn.set_authorizer(authorize)
            count = 0

            def progress():
                nonlocal count
                count += 1
                return int(count >= 100)

            conn.set_progress_handler(progress, 1000)
            cursor = conn.execute(bounded)
            columns = [column[0] for column in cursor.description or ()]
            rows = cursor.fetchmany(limit + 1)
        except sqlite3.Error:
            raise QueryRejected("SQLite query rejected or execution budget exceeded") from None
        finally:
            conn.close()
    else:
        raise QueryRejected("Unknown analytical engine")
    if len(columns) > 50:
        raise QueryRejected("Select at most 50 columns explicitly")
    if len(set(columns)) != len(columns):
        raise QueryRejected("Query output column names must be unique")
    clipped = []
    truncated_cells = False
    for row in rows[:limit]:
        result = []
        for cell in row:
            value = normalize(cell)
            if isinstance(value, str) and len(value) > 256:
                value = value[:256]
                truncated_cells = True
            result.append(value)
        clipped.append(result)
    return {
        "columns": columns,
        "rows": clipped,
        "truncated": len(rows) > limit or truncated_cells,
        "row_limit": limit,
        "cell_limit": 256,
    }
