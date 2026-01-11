#!/usr/bin/env python3
"""验证现有ClickHouse表结构并创建新的分析表."""

import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_clickhouse_client():
    """Get ClickHouse client."""
    try:
        from stock_datasource.models.database import db_client
        return db_client
    except Exception as e:
        logger.error(f"Failed to get ClickHouse client: {e}")
        return None

def verify_existing_tables():
    """验证现有表结构."""
    client = get_clickhouse_client()
    if not client:
        return False
    
    try:
        # 检查现有表
        existing_tables = ['user_positions', 'portfolio_analysis']
        
        for table in existing_tables:
            if client.table_exists(table):
                logger.info(f"✅ 表 '{table}' 已存在")
                schema = client.get_table_schema(table)
                logger.info(f"   列数: {len(schema)}")
                for col in schema[:3]:  # 显示前3列
                    logger.info(f"   - {col['column_name']}: {col['data_type']}")
            else:
                logger.warning(f"❌ 表 '{table}' 不存在，需要创建")
        
        return True
    except Exception as e:
        logger.error(f"验证表结构失败: {e}")
        return False

def create_clickhouse_portfolio_tables():
    """创建ClickHouse格式的持仓表."""
    client = get_clickhouse_client()
    if not client:
        return False
    
    try:
        # 创建或更新 user_positions 表
        user_positions_sql = """
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
            last_price_update DateTime DEFAULT now(),
            is_active UInt8 DEFAULT 1,
            created_at DateTime DEFAULT now(),
            updated_at DateTime DEFAULT now()
        ) ENGINE = ReplacingMergeTree(updated_at)
        ORDER BY (user_id, ts_code, id)
        PARTITION BY toYYYYMM(buy_date)
        SETTINGS index_granularity = 8192
        """
        
        client.create_table(user_positions_sql)
        logger.info("✅ user_positions 表创建成功")
        
        # 创建或更新 portfolio_analysis 表
        portfolio_analysis_sql = """
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
        PARTITION BY toYYYYMM(analysis_date)
        SETTINGS index_granularity = 8192
        """
        
        client.create_table(portfolio_analysis_sql)
        logger.info("✅ portfolio_analysis 表创建成功")
        
        return True
        
    except Exception as e:
        logger.error(f"创建表失败: {e}")
        return False

def create_new_analysis_tables():
    """创建新的分析表."""
    client = get_clickhouse_client()
    if not client:
        return False
    
    try:
        # 技术指标表
        technical_indicators_sql = """
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
        PARTITION BY toYYYYMM(indicator_date)
        SETTINGS index_granularity = 8192
        """
        
        client.create_table(technical_indicators_sql)
        logger.info("✅ technical_indicators 表创建成功")
        
        # 风险指标表
        portfolio_risk_metrics_sql = """
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
        PARTITION BY toYYYYMM(metric_date)
        SETTINGS index_granularity = 8192
        """
        
        client.create_table(portfolio_risk_metrics_sql)
        logger.info("✅ portfolio_risk_metrics 表创建成功")
        
        # 预警表
        position_alerts_sql = """
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
        PARTITION BY toYYYYMM(created_at)
        SETTINGS index_granularity = 8192
        """
        
        client.create_table(position_alerts_sql)
        logger.info("✅ position_alerts 表创建成功")
        
        return True
        
    except Exception as e:
        logger.error(f"创建新分析表失败: {e}")
        return False

def main():
    """主函数."""
    logger.info("🚀 开始验证和创建持仓管理表结构")
    logger.info("=" * 50)
    
    # 任务 1.1: 验证现有表结构
    logger.info("📋 任务 1.1: 验证现有ClickHouse表结构")
    if verify_existing_tables():
        logger.info("✅ 任务 1.1 完成")
    else:
        logger.warning("⚠️  任务 1.1 部分完成（可能是数据库连接问题）")
    
    # 任务 1.2: 创建新的分析表
    logger.info("\n📋 任务 1.2: 创建新的ClickHouse分析表")
    if create_clickhouse_portfolio_tables():
        logger.info("✅ 基础表创建完成")
    
    if create_new_analysis_tables():
        logger.info("✅ 分析表创建完成")
        logger.info("✅ 任务 1.2 完成")
    else:
        logger.warning("⚠️  任务 1.2 失败")
    
    logger.info("\n🎯 数据层准备阶段总结:")
    logger.info("   - user_positions: 用户持仓数据")
    logger.info("   - portfolio_analysis: 投资组合分析")
    logger.info("   - technical_indicators: 技术指标")
    logger.info("   - portfolio_risk_metrics: 风险指标")
    logger.info("   - position_alerts: 持仓预警")

if __name__ == "__main__":
    main()