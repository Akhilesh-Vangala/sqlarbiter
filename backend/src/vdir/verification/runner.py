"""Bounded in-memory SELECT runner for the known development schema.

These controls are defense in depth, not a production untrusted-code sandbox.
Production execution needs a separate isolated process/container boundary.
"""
import sqlite3


class QueryRejected(ValueError):
    pass


SCHEMA = """
CREATE TABLE orders(order_id TEXT PRIMARY KEY, business_date TEXT NOT NULL,
                    status TEXT NOT NULL);
CREATE TABLE order_items(item_id TEXT PRIMARY KEY, order_id TEXT NOT NULL,
                         product_id TEXT NOT NULL, amount_cents INTEGER NOT NULL);
CREATE TABLE product_versions(product_id TEXT NOT NULL, version INTEGER NOT NULL,
                              category TEXT NOT NULL, PRIMARY KEY(product_id, version));
"""


def run_query(snapshot, sql, *, max_rows=1000, max_progress_calls=100):
    if max_rows < 1 or max_progress_calls < 1:
        raise ValueError("Execution limits must be positive")
    if not isinstance(sql, str) or len(sql) > 50000:
        raise QueryRejected("SQL must be a string of at most 50000 characters")
    connection = sqlite3.connect(":memory:")
    try:
        connection.executescript(SCHEMA)
        connection.executemany("INSERT INTO orders VALUES (?, ?, ?)", snapshot.orders)
        connection.executemany("INSERT INTO order_items VALUES (?, ?, ?, ?)", snapshot.items)
        connection.executemany("INSERT INTO product_versions VALUES (?, ?, ?)", snapshot.products)
        connection.commit()
        connection.execute("PRAGMA query_only = ON")
        allowed_tables = {"orders", "order_items", "product_versions"}
        allowed_functions = {"sum", "count", "max", "min", "coalesce", "abs"}

        def authorize(action, first, second, database, trigger):
            if action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_RECURSIVE):
                return sqlite3.SQLITE_OK
            if action == sqlite3.SQLITE_READ and first in allowed_tables and database == "main":
                return sqlite3.SQLITE_OK
            if action == sqlite3.SQLITE_FUNCTION and second in allowed_functions:
                return sqlite3.SQLITE_OK
            return sqlite3.SQLITE_DENY

        calls = 0

        def limit_work():
            nonlocal calls
            calls += 1
            return int(calls >= max_progress_calls)

        connection.set_authorizer(authorize)
        connection.set_progress_handler(limit_work, 1000)
        cursor = connection.execute(sql)
        columns = tuple(column[0] for column in cursor.description or ())
        rows = cursor.fetchmany(max_rows + 1)
        if len(rows) > max_rows:
            raise QueryRejected("Result exceeds row budget")
        return columns, rows
    except (sqlite3.Error, sqlite3.Warning) as error:
        raise QueryRejected(str(error)) from error
    finally:
        connection.close()
