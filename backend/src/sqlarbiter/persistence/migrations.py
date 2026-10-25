"""Versioned PostgreSQL schema and LangGraph checkpoint initialization."""
import argparse
import asyncio
import os


SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    idempotency_key TEXT UNIQUE NOT NULL,
    request_json TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at DOUBLE PRECISION NOT NULL,
    updated_at DOUBLE PRECISION NOT NULL,
    owner TEXT,
    lease_until DOUBLE PRECISION,
    result_json TEXT,
    result_version TEXT,
    error TEXT
);
CREATE TABLE IF NOT EXISTS reviews (
    job_id TEXT PRIMARY KEY REFERENCES jobs(id),
    version TEXT NOT NULL,
    action TEXT NOT NULL,
    actor TEXT NOT NULL,
    note TEXT NOT NULL,
    created_at DOUBLE PRECISION NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    sequence BIGSERIAL PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES jobs(id),
    name TEXT NOT NULL,
    actor TEXT NOT NULL,
    created_at DOUBLE PRECISION NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS graph_continuations (
    parent_id TEXT PRIMARY KEY REFERENCES jobs(id),
    child_id TEXT UNIQUE NOT NULL REFERENCES jobs(id)
);
CREATE TABLE IF NOT EXISTS workflows (
    id TEXT PRIMARY KEY,
    idempotency_key TEXT UNIQUE NOT NULL,
    request_json TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    actor TEXT NOT NULL,
    created_at DOUBLE PRECISION NOT NULL
);
CREATE TABLE IF NOT EXISTS workflow_jobs (
    workflow_id TEXT NOT NULL REFERENCES workflows(id),
    job_id TEXT UNIQUE NOT NULL REFERENCES jobs(id),
    position INTEGER NOT NULL,
    PRIMARY KEY(workflow_id, position)
);
CREATE INDEX IF NOT EXISTS jobs_recent ON jobs(created_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS jobs_status_created ON jobs(status, created_at, id);
CREATE INDEX IF NOT EXISTS events_job_sequence ON events(job_id, sequence);
"""


def migrate(database_url):
    import psycopg

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(SCHEMA)
            cursor.execute(
                "INSERT INTO schema_migrations(version) VALUES (%s) ON CONFLICT DO NOTHING",
                (SCHEMA_VERSION,),
            )


async def setup_checkpoints(database_url):
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    async with AsyncPostgresSaver.from_conn_string(database_url) as saver:
        await saver.setup()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.getenv("SQLARBITER_DATABASE_URL"))
    parser.add_argument(
        "--checkpoint-database-url",
        default=os.getenv("SQLARBITER_CHECKPOINT_DATABASE_URL"),
    )
    args = parser.parse_args()
    if not args.database_url:
        parser.error("SQLARBITER_DATABASE_URL or --database-url is required")
    migrate(args.database_url)
    asyncio.run(setup_checkpoints(args.checkpoint_database_url or args.database_url))


if __name__ == "__main__":
    main()
