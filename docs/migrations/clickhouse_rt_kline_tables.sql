-- ClickHouse Migration: Create ODS Realtime Kline Tick Tables
-- Version: 1.0.0
-- Part of: add-realtime-kline-cache-sync

-- A Stock Market
CREATE TABLE IF NOT EXISTS {CLICKHOUSE_DATABASE}.ods_rt_kline_tick_cn (
    ts_code      LowCardinality(String)  COMMENT '证券代码',
    trade_date   Date                    COMMENT '交易日期',
    trade_time   String DEFAULT ''       COMMENT '交易时间',
    name         String DEFAULT ''       COMMENT '证券名称',
    open         Nullable(Float64)       COMMENT '开盘价',
    close        Nullable(Float64)       COMMENT '收盘价/最新价',
    high         Nullable(Float64)       COMMENT '最高价',
    low          Nullable(Float64)       COMMENT '最低价',
    pre_close    Nullable(Float64)       COMMENT '昨收价',
    vol          Nullable(Float64)       COMMENT '成交量',
    amount       Nullable(Float64)       COMMENT '成交额',
    pct_chg      Nullable(Float32)       COMMENT '涨跌幅(%)',
    bid          Nullable(Float64)       COMMENT '买一价',
    ask          Nullable(Float64)       COMMENT '卖一价',
    collected_at DateTime                COMMENT '采集时间',
    version      Int64                   COMMENT '版本号(毫秒)',
    INDEX idx_ts_code ts_code TYPE bloom_filter GRANULARITY 4
)
ENGINE = ReplacingMergeTree(version)
PARTITION BY toYYYYMM(trade_date)
ORDER BY (ts_code, trade_date, trade_time, version)
COMMENT 'A股实时日线 tick 数据';

-- ETF Market
CREATE TABLE IF NOT EXISTS {CLICKHOUSE_DATABASE}.ods_rt_kline_tick_etf (
    ts_code      LowCardinality(String)  COMMENT '证券代码',
    trade_date   Date                    COMMENT '交易日期',
    trade_time   String DEFAULT ''       COMMENT '交易时间',
    name         String DEFAULT ''       COMMENT '证券名称',
    open         Nullable(Float64)       COMMENT '开盘价',
    close        Nullable(Float64)       COMMENT '收盘价/最新价',
    high         Nullable(Float64)       COMMENT '最高价',
    low          Nullable(Float64)       COMMENT '最低价',
    pre_close    Nullable(Float64)       COMMENT '昨收价',
    vol          Nullable(Float64)       COMMENT '成交量',
    amount       Nullable(Float64)       COMMENT '成交额',
    pct_chg      Nullable(Float32)       COMMENT '涨跌幅(%)',
    bid          Nullable(Float64)       COMMENT '买一价',
    ask          Nullable(Float64)       COMMENT '卖一价',
    collected_at DateTime                COMMENT '采集时间',
    version      Int64                   COMMENT '版本号(毫秒)',
    INDEX idx_ts_code ts_code TYPE bloom_filter GRANULARITY 4
)
ENGINE = ReplacingMergeTree(version)
PARTITION BY toYYYYMM(trade_date)
ORDER BY (ts_code, trade_date, trade_time, version)
COMMENT 'ETF实时日线 tick 数据';

-- Index Market
CREATE TABLE IF NOT EXISTS {CLICKHOUSE_DATABASE}.ods_rt_kline_tick_index (
    ts_code      LowCardinality(String)  COMMENT '证券代码',
    trade_date   Date                    COMMENT '交易日期',
    trade_time   String DEFAULT ''       COMMENT '交易时间',
    name         String DEFAULT ''       COMMENT '证券名称',
    open         Nullable(Float64)       COMMENT '开盘价',
    close        Nullable(Float64)       COMMENT '收盘价/最新价',
    high         Nullable(Float64)       COMMENT '最高价',
    low          Nullable(Float64)       COMMENT '最低价',
    pre_close    Nullable(Float64)       COMMENT '昨收价',
    vol          Nullable(Float64)       COMMENT '成交量',
    amount       Nullable(Float64)       COMMENT '成交额',
    pct_chg      Nullable(Float32)       COMMENT '涨跌幅(%)',
    bid          Nullable(Float64)       COMMENT '买一价',
    ask          Nullable(Float64)       COMMENT '卖一价',
    collected_at DateTime                COMMENT '采集时间',
    version      Int64                   COMMENT '版本号(毫秒)',
    INDEX idx_ts_code ts_code TYPE bloom_filter GRANULARITY 4
)
ENGINE = ReplacingMergeTree(version)
PARTITION BY toYYYYMM(trade_date)
ORDER BY (ts_code, trade_date, trade_time, version)
COMMENT '指数实时日线 tick 数据';

-- HK Market
CREATE TABLE IF NOT EXISTS {CLICKHOUSE_DATABASE}.ods_rt_kline_tick_hk (
    ts_code      LowCardinality(String)  COMMENT '证券代码',
    trade_date   Date                    COMMENT '交易日期',
    trade_time   String DEFAULT ''       COMMENT '交易时间',
    name         String DEFAULT ''       COMMENT '证券名称',
    open         Nullable(Float64)       COMMENT '开盘价',
    close        Nullable(Float64)       COMMENT '收盘价/最新价',
    high         Nullable(Float64)       COMMENT '最高价',
    low          Nullable(Float64)       COMMENT '最低价',
    pre_close    Nullable(Float64)       COMMENT '昨收价',
    vol          Nullable(Float64)       COMMENT '成交量',
    amount       Nullable(Float64)       COMMENT '成交额',
    pct_chg      Nullable(Float32)       COMMENT '涨跌幅(%)',
    bid          Nullable(Float64)       COMMENT '买一价',
    ask          Nullable(Float64)       COMMENT '卖一价',
    collected_at DateTime                COMMENT '采集时间',
    version      Int64                   COMMENT '版本号(毫秒)',
    INDEX idx_ts_code ts_code TYPE bloom_filter GRANULARITY 4
)
ENGINE = ReplacingMergeTree(version)
PARTITION BY toYYYYMM(trade_date)
ORDER BY (ts_code, trade_date, trade_time, version)
COMMENT '港股实时日线 tick 数据';
