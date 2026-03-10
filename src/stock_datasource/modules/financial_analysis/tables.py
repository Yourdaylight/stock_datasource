"""ClickHouse table definitions for financial analysis module."""

import logging

from stock_datasource.models.database import db_client

logger = logging.getLogger(__name__)

FINANCIAL_ANALYSIS_TABLES: dict[str, str] = {
    "report_analysis_records": """
        CREATE TABLE IF NOT EXISTS report_analysis_records (
            id String,
            ts_code LowCardinality(String),
            stock_name String DEFAULT '',
            market LowCardinality(String) DEFAULT 'A',
            end_date String,
            report_type String DEFAULT '',
            analysis_type String DEFAULT 'comprehensive',
            report_content String,
            data_snapshot String DEFAULT '',
            health_score Float32 DEFAULT 0,
            analysis_sections String DEFAULT '',
            analysis_metadata String DEFAULT '',
            created_at DateTime DEFAULT now(),
            updated_at DateTime DEFAULT now()
        ) ENGINE = ReplacingMergeTree(updated_at)
        ORDER BY (ts_code, end_date, analysis_type, id)
        PARTITION BY toYYYYMM(created_at)
        SETTINGS index_granularity = 8192
    """,
}


def ensure_financial_analysis_tables() -> list[str]:
    """Create all financial analysis tables if not exist. Return list of created table names."""
    created = []
    for table_name, create_sql in FINANCIAL_ANALYSIS_TABLES.items():
        try:
            if not db_client.table_exists(table_name):
                db_client.execute(create_sql)
                logger.info(f"Created financial analysis table: {table_name}")
                created.append(table_name)
            else:
                logger.debug(f"Financial analysis table already exists: {table_name}")
        except Exception as e:
            logger.error(f"Failed to create financial analysis table {table_name}: {e}")
    return created
