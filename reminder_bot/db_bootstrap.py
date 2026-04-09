import os
import sqlite3
import subprocess
import sys

import structlog

from reminder_bot.config import settings

logger = structlog.get_logger()


def parse_sqlite_path(database_url: str) -> str:
    if database_url.startswith("sqlite+aiosqlite:///"):
        return database_url[21:]
    if database_url.startswith("sqlite:///"):
        return database_url[10:]
    return database_url


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    """Check if a table exists in the database."""
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,)
    )
    return cursor.fetchone() is not None


def column_exists(conn: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    cursor = conn.execute(f"PRAGMA table_info({table_name})")
    rows = cursor.fetchall()
    return any(row[1] == column_name for row in rows)


def add_column_if_missing(
    conn: sqlite3.Connection, table_name: str, column_name: str, column_def: str
) -> None:
    """Add a column to a table if it doesn't already exist."""
    if not column_exists(conn, table_name, column_name):
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}")
        conn.commit()
        logger.info("added_column", table=table_name, column=column_name)


def run_alembic_command(command: list[str]) -> None:
    """Execute an alembic command via subprocess."""
    result = subprocess.run(
        ["/app/.venv/bin/alembic"] + command, capture_output=True, text=True, cwd="/app"
    )
    if result.returncode != 0:
        logger.error("alembic_failed", stdout=result.stdout, stderr=result.stderr)
        raise RuntimeError(f"Alembic command failed: {result.stderr}")
    logger.info("alembic_command_success", command=command)


def bootstrap_database() -> None:
    database_url = settings.constructed_database_url

    if ":memory:" in database_url:
        logger.info("in_memory_database_skip_bootstrap")
        return

    if database_url.startswith("postgresql") or database_url.startswith("postgres"):
        logger.info("postgresql_database_running_migrations")
        run_alembic_command(["upgrade", "head"])
        return

    if not database_url.startswith("sqlite"):
        logger.info("non_sqlite_database_skip_bootstrap")
        return

    db_path = parse_sqlite_path(database_url)

    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        has_reminders = table_exists(conn, "reminders")
        has_alembic_version = table_exists(conn, "alembic_version")

        if not has_reminders:
            logger.info("fresh_database_running_migrations")
            run_alembic_command(["upgrade", "head"])
        elif has_reminders and not has_alembic_version:
            logger.info("legacy_database_adding_columns_and_stamping")
            add_column_if_missing(conn, "reminders", "weekday", "INTEGER")
            add_column_if_missing(conn, "reminders", "cron_expression", "VARCHAR(100)")
            run_alembic_command(["stamp", "head"])
        else:
            logger.info("database_already_managed_by_alembic")
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        bootstrap_database()
    except Exception as e:
        logger.error("bootstrap_failed", error=str(e))
        sys.exit(1)
