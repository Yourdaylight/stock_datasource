-- Migration: 001_create_system_structured_logs
-- Created: 2026-04-09
-- Description: Create system_structured_logs table for request-tracing and log analysis
--              (JSONL-imported log records with request correlation)
-- NOTE: Do NOT include database prefix — db_client already targets stock_datasource.

CREATE TABLE IF NOT EXISTS system_structured_logs
(
    timestamp   DateTime64(3),
    level       LowCardinality(String),
    request_id  String DEFAULT '-',
    user_id     String DEFAULT '-',
    module      String,
    function    String,
    line        UInt32,
    message     String,
    exception   Nullable(String),
    extra       String DEFAULT '{}'
)
ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(timestamp)
ORDER BY (timestamp, level, request_id)
TTL toDateTime(timestamp) + INTERVAL 90 DAY
SETTINGS index_granularity = 8192;
