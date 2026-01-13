"""Top list (龙虎榜) module initialization."""

import logging
from stock_datasource.models.database import db_client

logger = logging.getLogger(__name__)


def init_toplist_tables():
    """Initialize top list related tables."""
    
    # Create top_list table
    top_list_sql = """
    CREATE TABLE IF NOT EXISTS ods_top_list (
        trade_date Date,
        ts_code LowCardinality(String),
        name String,
        close Nullable(Float64),
        pct_chg Nullable(Float64),
        turnover_rate Nullable(Float64),
        amount Nullable(Float64),
        l_sell Nullable(Float64),
        l_buy Nullable(Float64),
        l_amount Nullable(Float64),
        net_amount Nullable(Float64),
        net_rate Nullable(Float64),
        amount_rate Nullable(Float64),
        float_values Nullable(Float64),
        reason String,
        version UInt32 DEFAULT toUInt32(toUnixTimestamp(now())),
        _ingested_at DateTime DEFAULT now()
    ) ENGINE = ReplacingMergeTree(version)
    PARTITION BY toYYYYMM(trade_date)
    ORDER BY (trade_date, ts_code)
    COMMENT 'Top list (龙虎榜) data from TuShare API'
    """
    
    # Create top_inst table
    top_inst_sql = """
    CREATE TABLE IF NOT EXISTS ods_top_inst (
        trade_date Date,
        ts_code LowCardinality(String),
        exalter String,
        buy Nullable(Float64),
        buy_rate Nullable(Float64),
        sell Nullable(Float64),
        sell_rate Nullable(Float64),
        net_buy Nullable(Float64),
        seat_type Enum8('institution' = 1, 'hot_money' = 2, 'unknown' = 3) DEFAULT 'unknown',
        version UInt32 DEFAULT toUInt32(toUnixTimestamp(now())),
        _ingested_at DateTime DEFAULT now()
    ) ENGINE = ReplacingMergeTree(version)
    PARTITION BY toYYYYMM(trade_date)
    ORDER BY (trade_date, ts_code, exalter)
    COMMENT 'Top institutional seats (机构席位) data from TuShare API'
    """
    
    # Create seat classification table
    seat_classification_sql = """
    CREATE TABLE IF NOT EXISTS dim_seat_classification (
        seat_name String,
        seat_type Enum8('institution' = 1, 'hot_money' = 2, 'unknown' = 3),
        classification_confidence Float32,
        created_at DateTime DEFAULT now(),
        updated_at DateTime DEFAULT now()
    ) ENGINE = ReplacingMergeTree(updated_at)
    ORDER BY seat_name
    COMMENT 'Seat classification for top list analysis'
    """
    
    # Create top list analysis summary table
    top_list_summary_sql = """
    CREATE TABLE IF NOT EXISTS fact_top_list_summary (
        trade_date Date,
        total_stocks UInt32,
        total_amount Float64,
        institution_count UInt32,
        hot_money_count UInt32,
        avg_pct_chg Float64,
        avg_turnover_rate Float64,
        net_institution_flow Float64,
        net_hot_money_flow Float64,
        version UInt32 DEFAULT toUInt32(toUnixTimestamp(now())),
        _ingested_at DateTime DEFAULT now()
    ) ENGINE = ReplacingMergeTree(version)
    PARTITION BY toYYYYMM(trade_date)
    ORDER BY trade_date
    COMMENT 'Daily top list summary statistics'
    """
    
    try:
        # Create tables
        db_client.execute(top_list_sql)
        logger.info("Created ods_top_list table")
        
        db_client.execute(top_inst_sql)
        logger.info("Created ods_top_inst table")
        
        db_client.execute(seat_classification_sql)
        logger.info("Created dim_seat_classification table")
        
        db_client.execute(top_list_summary_sql)
        logger.info("Created fact_top_list_summary table")
        
        logger.info("Top list tables initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize top list tables: {e}")
        raise


if __name__ == "__main__":
    init_toplist_tables()