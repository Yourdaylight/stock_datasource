-- MCP API Keys: independent from JWT, used by external MCP clients (Claude Code, Cursor, etc.)
CREATE TABLE IF NOT EXISTS mcp_api_keys (
    id String,
    user_id String,
    key_name String DEFAULT '',
    api_key_hash String,
    api_key_prefix String DEFAULT '',
    is_active UInt8 DEFAULT 1,
    last_used_at Nullable(DateTime) DEFAULT NULL,
    expires_at Nullable(DateTime) DEFAULT NULL,
    created_at DateTime DEFAULT now(),
    updated_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (user_id, id)
SETTINGS index_granularity = 8192;
