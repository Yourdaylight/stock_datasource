"""ClickHouse table definitions for sentinel system."""

from stock_datasource.models.database import db_client

TABLES = {
    "sentinel_alerts": """
        CREATE TABLE IF NOT EXISTS sentinel_alerts (
            alert_id String,
            sentinel_type String,
            category String,
            severity String,
            ts_code Nullable(String),
            sector_code Nullable(String),
            index_code Nullable(String),
            signal_type String,
            description String,
            metric_name String,
            metric_value Float64,
            threshold Float64,
            deviation_pct Float64,
            context String,
            created_at DateTime DEFAULT now()
        ) ENGINE = MergeTree()
        ORDER BY (created_at, sentinel_type)
        TTL created_at + INTERVAL 90 DAY
    """,
    "sentinel_analyst_reports": """
        CREATE TABLE IF NOT EXISTS sentinel_analyst_reports (
            report_id String,
            analyst_type String,
            trigger_count UInt32,
            market_regime Nullable(String),
            overall_conviction Float64,
            insights_json String,
            source_alert_ids Array(String),
            created_at DateTime DEFAULT now()
        ) ENGINE = MergeTree()
        ORDER BY (created_at, analyst_type)
        TTL created_at + INTERVAL 90 DAY
    """,
    "sentinel_decisions": """
        CREATE TABLE IF NOT EXISTS sentinel_decisions (
            decision_id String,
            trade_date String,
            market_regime String,
            market_risk_level String,
            suggested_position Float64,
            buy_count UInt32,
            sell_count UInt32,
            confidence Float64,
            decision_json String,
            created_at DateTime DEFAULT now()
        ) ENGINE = MergeTree()
        ORDER BY (trade_date, created_at)
        TTL created_at + INTERVAL 365 DAY
    """,
}


def ensure_sentinel_tables() -> None:
    """Create sentinel tables if they don't exist."""
    for table_name, ddl in TABLES.items():
        try:
            db_client.execute_query(ddl)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(
                "Failed to create table %s: %s", table_name, e
            )
