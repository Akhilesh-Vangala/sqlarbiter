"""Wait for the migrated PostgreSQL schema before starting an API or worker pod."""
import os
import sys
import time


def main():
    import psycopg

    database_url = os.getenv("VDIR_DATABASE_URL")
    if not database_url:
        raise SystemExit("VDIR_DATABASE_URL is required")
    deadline = time.monotonic() + float(os.getenv("VDIR_DATABASE_WAIT_SECONDS", "120"))
    last_error = None
    while time.monotonic() < deadline:
        try:
            with psycopg.connect(database_url, connect_timeout=5) as connection:
                row = connection.execute(
                    "SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1"
                ).fetchone()
                if row:
                    print("PostgreSQL schema is ready", flush=True)
                    return
        except (psycopg.Error, OSError) as error:
            last_error = error.__class__.__name__
        time.sleep(1)
    print("PostgreSQL schema did not become ready: " + str(last_error or "missing migration"), file=sys.stderr)
    raise SystemExit(1)


if __name__ == "__main__":
    main()
