"""Incremental ClickHouse migration runner.

Migrations are SQL files in ``docker/migrations/`` named like:
    001_create_system_structured_logs.sql
    002_add_some_column.sql

A tracking table (``stock_datasource._migrations``) records which ones have
been applied.  :func:`run_pending_migrations` is idempotent — safe to call
on every startup.

Each migration file must be a single valid ClickHouse DDL statement
(CREATE TABLE IF NOT EXISTS, ALTER TABLE … ADD COLUMN, etc.).
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "docker" / "migrations"

_TRACKING_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS _migrations
(
    version     String,
    applied_at  DateTime DEFAULT now()
)
ENGINE = TinyLog
"""


def _ensure_tracking_table(db) -> None:
    """Create the _migrations tracking table if it doesn't exist."""
    try:
        db.query(_TRACKING_TABLE_DDL)
    except Exception:
        # Table may already exist or DB not reachable — that's OK
        pass


def _get_applied_versions(db) -> set[str]:
    """Return the set of already-applied migration version strings."""
    try:
        rows = db.query("SELECT version FROM _migrations")
        return {row[0] for row in rows}
    except Exception:
        return set()


def run_pending_migrations() -> int:
    """Run all pending ClickHouse migrations.

    Returns:
        Number of newly applied migrations.
    """
    if not _MIGRATIONS_DIR.is_dir():
        logger.debug("No migrations directory found, skipping.")
        return 0

    from stock_datasource.models.database import db_client

    _ensure_tracking_table(db_client)
    applied = _get_applied_versions(db_client)

    sql_files = sorted(_MIGRATIONS_DIR.glob("*.sql"))
    if not sql_files:
        return 0

    newly_applied = 0
    for sql_file in sql_files:
        version = sql_file.stem  # e.g. "001_create_system_structured_logs"
        if version in applied:
            continue

        sql = sql_file.read_text(encoding="utf-8").strip()
        if not sql:
            continue

        try:
            # Execute the migration DDL
            db_client.query(sql)
            # Record success
            # NOTE: Do not use parameterized INSERT — the HTTP client sends
            # query as plain text and ClickHouse VALUES parser cannot handle
            # the %(v)s placeholder.  Version strings are controlled by us
            # (filenames), so injection is not a concern.
            safe_version = version.replace("'", "''")
            db_client.query(
                f"INSERT INTO _migrations (version) VALUES ('{safe_version}')"
            )
            logger.info(f"Migration {version} applied successfully")
            newly_applied += 1
        except Exception as e:
            logger.error(f"Migration {version} FAILED: {e}")
            # Stop on first failure to maintain consistency
            raise

    if newly_applied == 0:
        logger.info("All ClickHouse migrations up to date.")
    else:
        logger.info(f"Applied {newly_applied} ClickHouse migration(s).")

    return newly_applied
