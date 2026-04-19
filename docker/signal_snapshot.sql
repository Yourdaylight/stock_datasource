-- ============================================================
-- Signal Snapshot Table: obs_stock_signal_snapshot
-- 粒度: 每只股票每天一条记录
-- 引擎: ReplacingMergeTree (按 ts_code + signal_date 去重)
-- ============================================================

CREATE TABLE IF NOT EXISTS obs_stock_signal_snapshot
(
    ts_code         String COMMENT '股票代码, 如 600519.SH',
    signal_date     String COMMENT '信号日期, 格式 YYYYMMDD',
    news_score      Float64 DEFAULT 50.0 COMMENT '消息面评分 0-100',
    capital_score   Float64 DEFAULT 50.0 COMMENT '资金面评分 0-100',
    tech_score      Float64 DEFAULT 50.0 COMMENT '技术面评分 0-100',
    composite_score Float64 DEFAULT 50.0 COMMENT '综合评分 0-100',
    news_detail     String DEFAULT '{}' COMMENT '消息面评分细节JSON',
    capital_detail  String DEFAULT '{}' COMMENT '资金面评分细节JSON',
    created_at      DateTime DEFAULT now() COMMENT '创建时间'
)
ENGINE = ReplacingMergeTree()
PARTITION BY toYYYYMM(toDate(signal_date, '%Y%m%d'))
ORDER BY (ts_code, signal_date)
TTL created_at + INTERVAL 365 DAY
COMMENT '股票信号聚合评分快照表';

-- 常用查询索引说明:
-- 1. 按股票+日期范围查询: WHERE ts_code = ? AND signal_date >= ?
-- 2. 按日期查全市场排名: WHERE signal_date = ? ORDER BY composite_score DESC
-- 3. 时序趋势: WHERE ts_code = ? ORDER BY signal_date ASC
