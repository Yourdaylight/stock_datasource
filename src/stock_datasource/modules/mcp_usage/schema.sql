-- MCP Tool Usage Log: records each MCP tool call with table and record count
CREATE TABLE IF NOT EXISTS mcp_tool_usage_log (
    id String,
    user_id String,
    api_key_id String DEFAULT '',
    tool_name String,
    service_prefix String DEFAULT '',
    table_name String DEFAULT '',
    arguments String DEFAULT '',
    record_count Int64 DEFAULT 0,
    duration_ms Int64 DEFAULT 0,
    is_error UInt8 DEFAULT 0,
    error_message String DEFAULT '',
    created_at DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (user_id, created_at, id)
PARTITION BY toYYYYMM(created_at)
SETTINGS index_granularity = 8192;
