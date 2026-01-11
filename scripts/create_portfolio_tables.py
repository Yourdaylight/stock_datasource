#!/usr/bin/env python3
"""
创建持仓管理相关数据表
"""

import logging

logger = logging.getLogger(__name__)

# 持仓管理相关SQL语句
PORTFOLIO_TABLES_SQL = """
-- 用户持仓分析表
CREATE TABLE IF NOT EXISTS user_portfolio_analysis (
    id String,
    user_id String DEFAULT 'default_user',
    analysis_date Date,
    total_value Decimal(15, 2),
    total_cost Decimal(15, 2),
    total_profit Decimal(15, 2),
    profit_rate Decimal(8, 4),
    daily_change Decimal(15, 2),
    daily_change_rate Decimal(8, 4),
    position_count UInt32,
    risk_score Decimal(5, 2),
    analysis_summary String,
    created_at DateTime DEFAULT now(),
    updated_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (user_id, analysis_date, id)
SETTINGS index_granularity = 8192;

-- 每日分析报告表
CREATE TABLE IF NOT EXISTS daily_analysis_reports (
    id String,
    user_id String DEFAULT 'default_user',
    report_date Date,
    report_type Enum8('daily' = 1, 'weekly' = 2, 'monthly' = 3),
    market_analysis String,
    portfolio_summary String,
    individual_analysis String,
    risk_assessment String,
    recommendations String,
    ai_insights String,
    status Enum8('pending' = 1, 'completed' = 2, 'failed' = 3) DEFAULT 'pending',
    created_at DateTime DEFAULT now(),
    updated_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (user_id, report_date, report_type, id)
SETTINGS index_granularity = 8192;

-- 持仓历史数据表
CREATE TABLE IF NOT EXISTS position_history (
    id String,
    position_id String,
    user_id String DEFAULT 'default_user',
    ts_code String,
    stock_name String,
    quantity UInt32,
    cost_price Decimal(10, 3),
    current_price Decimal(10, 3),
    market_value Decimal(15, 2),
    profit_loss Decimal(15, 2),
    profit_rate Decimal(8, 4),
    record_date Date,
    record_time DateTime DEFAULT now(),
    change_type Enum8('create' = 1, 'update' = 2, 'delete' = 3, 'price_update' = 4),
    created_at DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (user_id, position_id, record_date, record_time)
SETTINGS index_granularity = 8192;
"""

def create_portfolio_tables():
    """创建持仓管理相关数据表"""
    try:
        # 这里暂时只记录SQL，实际执行需要数据库连接
        logger.info("持仓管理数据表SQL已准备完成")
        logger.info("包含表: user_portfolio_analysis, daily_analysis_reports, position_history")
        
        # 将SQL保存到文件供后续使用
        with open('/tmp/portfolio_tables.sql', 'w', encoding='utf-8') as f:
            f.write(PORTFOLIO_TABLES_SQL)
        
        logger.info("SQL文件已保存到 /tmp/portfolio_tables.sql")
        return True
        
    except Exception as e:
        logger.error(f"创建数据表失败: {e}")
        return False

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    if create_portfolio_tables():
        print("✅ 数据表准备完成")
    else:
        print("❌ 数据表准备失败")