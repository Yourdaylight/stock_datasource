"""Portfolio module initialization."""

import logging
from stock_datasource.models.database import db_client

logger = logging.getLogger(__name__)


def ensure_portfolio_tables():
    """Ensure portfolio tables exist in ClickHouse."""
    try:
        client = db_client
        
        # Create user_positions table if not exists
        client.execute("""
        CREATE TABLE IF NOT EXISTS user_positions (
            id String,
            user_id String DEFAULT 'default_user',
            ts_code String,
            stock_name String,
            quantity UInt32,
            cost_price Decimal(10, 3),
            buy_date Date,
            current_price Nullable(Decimal(10, 3)),
            market_value Nullable(Decimal(15, 2)),
            profit_loss Nullable(Decimal(15, 2)),
            profit_rate Nullable(Decimal(8, 4)),
            notes String DEFAULT '',
            sector String DEFAULT '',
            industry String DEFAULT '',
            last_price_update DateTime,
            is_active UInt8 DEFAULT 1,
            created_at DateTime DEFAULT now(),
            updated_at DateTime DEFAULT now()
        ) ENGINE = ReplacingMergeTree(updated_at)
        ORDER BY (user_id, ts_code, id)
        SETTINGS index_granularity = 8192
        """)
        
        # Create portfolio_analysis table if not exists
        client.execute("""
        CREATE TABLE IF NOT EXISTS portfolio_analysis (
            id String,
            user_id String DEFAULT 'default_user',
            analysis_date Date,
            analysis_type Enum8('daily' = 1, 'weekly' = 2, 'monthly' = 3, 'manual' = 4),
            analysis_summary String,
            stock_analyses String,
            risk_alerts String,
            recommendations String,
            market_sentiment String DEFAULT '',
            technical_signals String DEFAULT '',
            fundamental_scores String DEFAULT '',
            created_at DateTime DEFAULT now(),
            updated_at DateTime DEFAULT now()
        ) ENGINE = ReplacingMergeTree(updated_at)
        ORDER BY (user_id, analysis_date, analysis_type, id)
        SETTINGS index_granularity = 8192
        """)
        
        # Create technical_indicators table if not exists
        client.execute("""
        CREATE TABLE IF NOT EXISTS technical_indicators (
            id String,
            ts_code String,
            indicator_date Date,
            ma5 Nullable(Decimal(10, 3)),
            ma10 Nullable(Decimal(10, 3)),
            ma20 Nullable(Decimal(10, 3)),
            ma60 Nullable(Decimal(10, 3)),
            macd Nullable(Decimal(10, 6)),
            macd_signal Nullable(Decimal(10, 6)),
            macd_hist Nullable(Decimal(10, 6)),
            rsi Nullable(Decimal(8, 4)),
            kdj_k Nullable(Decimal(8, 4)),
            kdj_d Nullable(Decimal(8, 4)),
            kdj_j Nullable(Decimal(8, 4)),
            bollinger_upper Nullable(Decimal(10, 3)),
            bollinger_middle Nullable(Decimal(10, 3)),
            bollinger_lower Nullable(Decimal(10, 3)),
            created_at DateTime DEFAULT now(),
            updated_at DateTime DEFAULT now()
        ) ENGINE = ReplacingMergeTree(updated_at)
        ORDER BY (ts_code, indicator_date, id)
        SETTINGS index_granularity = 8192
        """)
        
        # Create portfolio_risk_metrics table if not exists
        client.execute("""
        CREATE TABLE IF NOT EXISTS portfolio_risk_metrics (
            id String,
            user_id String DEFAULT 'default_user',
            metric_date Date,
            total_value Decimal(15, 2),
            var_95 Nullable(Decimal(15, 2)),
            var_99 Nullable(Decimal(15, 2)),
            max_drawdown Nullable(Decimal(8, 4)),
            sharpe_ratio Nullable(Decimal(8, 4)),
            beta Nullable(Decimal(8, 4)),
            volatility Nullable(Decimal(8, 4)),
            concentration_risk Nullable(Decimal(8, 4)),
            sector_exposure String DEFAULT '',
            created_at DateTime DEFAULT now(),
            updated_at DateTime DEFAULT now()
        ) ENGINE = ReplacingMergeTree(updated_at)
        ORDER BY (user_id, metric_date, id)
        SETTINGS index_granularity = 8192
        """)
        
        # Create position_alerts table if not exists
        client.execute("""
        CREATE TABLE IF NOT EXISTS position_alerts (
            id String,
            user_id String DEFAULT 'default_user',
            ts_code String,
            alert_type Enum8('price' = 1, 'profit_loss' = 2, 'volume' = 3, 'technical' = 4),
            condition_type Enum8('greater_than' = 1, 'less_than' = 2, 'equal' = 3),
            threshold_value Decimal(15, 6),
            current_value Nullable(Decimal(15, 6)),
            is_triggered UInt8 DEFAULT 0,
            is_active UInt8 DEFAULT 1,
            message String DEFAULT '',
            created_at DateTime DEFAULT now(),
            updated_at DateTime DEFAULT now(),
            triggered_at Nullable(DateTime)
        ) ENGINE = ReplacingMergeTree(updated_at)
        ORDER BY (user_id, ts_code, alert_type, id)
        SETTINGS index_granularity = 8192
        """)
        
        logger.info("Portfolio tables ensured successfully")
        
    except Exception as e:
        logger.error(f"Failed to ensure portfolio tables: {e}")
        raise