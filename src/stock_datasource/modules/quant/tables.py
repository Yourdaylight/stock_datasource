"""ClickHouse table definitions for quant module."""

import logging

from stock_datasource.models.database import db_client

logger = logging.getLogger(__name__)

QUANT_TABLES: dict[str, str] = {
    "quant_screening_result": """
        CREATE TABLE IF NOT EXISTS quant_screening_result (
            run_date Date,
            run_id String,
            ts_code String,
            stock_name String,
            pass_traditional UInt8,
            pass_custom UInt8,
            pass_benford UInt8,
            overall_pass UInt8,
            reject_reasons Array(String),
            rule_details String DEFAULT '',
            roe_3y_avg Float64 DEFAULT 0,
            revenue_growth_2y Array(Float64),
            net_profit Float64 DEFAULT 0,
            cashflow_sync_ratio Float64 DEFAULT 0,
            expense_anomaly_score Float64 DEFAULT 0,
            receivable_revenue_gap Float64 DEFAULT 0,
            benford_chi2 Float64 DEFAULT 0,
            benford_p_value Float64 DEFAULT 0,
            created_at DateTime DEFAULT now()
        ) ENGINE = ReplacingMergeTree()
        ORDER BY (run_date, ts_code)
    """,

    "quant_screening_run_stats": """
        CREATE TABLE IF NOT EXISTS quant_screening_run_stats (
            run_date Date,
            run_id String,
            total_stocks UInt32,
            passed_count UInt32,
            rejected_count UInt32,
            rule_stats String DEFAULT '',
            data_readiness String DEFAULT '',
            execution_time_ms UInt64 DEFAULT 0,
            status String DEFAULT 'success',
            error_message String DEFAULT '',
            created_at DateTime DEFAULT now()
        ) ENGINE = ReplacingMergeTree()
        ORDER BY (run_date, run_id)
    """,

    "quant_rps_rank": """
        CREATE TABLE IF NOT EXISTS quant_rps_rank (
            calc_date Date,
            ts_code String,
            stock_name String,
            rps_250 Float64 DEFAULT 0,
            rps_120 Float64 DEFAULT 0,
            rps_60 Float64 DEFAULT 0,
            price_chg_250 Float64 DEFAULT 0,
            price_chg_120 Float64 DEFAULT 0,
            price_chg_60 Float64 DEFAULT 0,
            created_at DateTime DEFAULT now()
        ) ENGINE = ReplacingMergeTree()
        ORDER BY (calc_date, ts_code)
    """,

    "quant_core_pool": """
        CREATE TABLE IF NOT EXISTS quant_core_pool (
            update_date Date,
            pool_type String,
            ts_code String,
            stock_name String,
            quality_score Float64 DEFAULT 0,
            growth_score Float64 DEFAULT 0,
            value_score Float64 DEFAULT 0,
            momentum_score Float64 DEFAULT 0,
            total_score Float64 DEFAULT 0,
            factor_details String DEFAULT '',
            rank UInt32 DEFAULT 0,
            rps_250 Float64 DEFAULT 0,
            entry_date Date DEFAULT today(),
            exit_date Nullable(Date),
            change_type String DEFAULT '',
            created_at DateTime DEFAULT now()
        ) ENGINE = ReplacingMergeTree()
        ORDER BY (update_date, pool_type, ts_code)
    """,

    "quant_trading_signal": """
        CREATE TABLE IF NOT EXISTS quant_trading_signal (
            signal_date Date,
            ts_code String,
            stock_name String,
            signal_type String,
            signal_source String,
            price Float64 DEFAULT 0,
            target_position Float64 DEFAULT 0,
            confidence Float64 DEFAULT 0,
            reason String DEFAULT '',
            pool_type String DEFAULT '',
            ma25 Float64 DEFAULT 0,
            ma120 Float64 DEFAULT 0,
            signal_context String DEFAULT '',
            created_at DateTime DEFAULT now()
        ) ENGINE = MergeTree()
        ORDER BY (signal_date, ts_code)
        TTL signal_date + INTERVAL 365 DAY
    """,

    "quant_deep_analysis": """
        CREATE TABLE IF NOT EXISTS quant_deep_analysis (
            analysis_date Date,
            ts_code String,
            stock_name String,
            tech_score Float64 DEFAULT 0,
            mgmt_discussion_score Float64 DEFAULT 0,
            prospect_score Float64 DEFAULT 0,
            key_findings Array(String),
            risk_factors Array(String),
            verification_points Array(String),
            ai_summary String DEFAULT '',
            tech_snapshot String DEFAULT '',
            created_at DateTime DEFAULT now()
        ) ENGINE = ReplacingMergeTree()
        ORDER BY (analysis_date, ts_code)
    """,

    "quant_model_config": """
        CREATE TABLE IF NOT EXISTS quant_model_config (
            config_id String,
            config_name String,
            config_type String,
            config_data String DEFAULT '',
            is_active UInt8 DEFAULT 1,
            user_id String DEFAULT '',
            updated_at DateTime DEFAULT now()
        ) ENGINE = ReplacingMergeTree()
        ORDER BY (config_id)
    """,

    "quant_pipeline_run": """
        CREATE TABLE IF NOT EXISTS quant_pipeline_run (
            run_id String,
            run_date Date,
            pipeline_type String,
            stages String DEFAULT '',
            overall_status String DEFAULT 'pending',
            triggered_by String DEFAULT 'manual',
            created_at DateTime DEFAULT now(),
            updated_at DateTime DEFAULT now()
        ) ENGINE = ReplacingMergeTree()
        ORDER BY (run_date, run_id)
    """,
}


def ensure_quant_tables() -> list[str]:
    """Create all quant tables if not exist. Return list of created table names."""
    created = []
    for table_name, create_sql in QUANT_TABLES.items():
        try:
            if not db_client.table_exists(table_name):
                db_client.execute(create_sql)
                logger.info(f"Created quant table: {table_name}")
                created.append(table_name)
            else:
                logger.debug(f"Quant table already exists: {table_name}")
        except Exception as e:
            logger.error(f"Failed to create quant table {table_name}: {e}")
    return created
