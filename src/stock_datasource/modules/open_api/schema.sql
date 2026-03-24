-- Open API Gateway: access policies (which plugin endpoints are open, rate limits, etc.)
CREATE TABLE IF NOT EXISTS api_access_policies (
    policy_id String,
    api_path String,
    api_type Enum8('http' = 1, 'mcp' = 2, 'both' = 3) DEFAULT 'http',
    is_enabled UInt8 DEFAULT 0,
    rate_limit_per_min UInt32 DEFAULT 60,
    rate_limit_per_day UInt32 DEFAULT 10000,
    max_records UInt32 DEFAULT 5000,
    description String DEFAULT '',
    created_at DateTime DEFAULT now(),
    updated_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (api_path, api_type)
SETTINGS index_granularity = 8192;

-- Open API Gateway: unified usage log
CREATE TABLE IF NOT EXISTS api_usage_log (
    log_id String,
    api_path String,
    api_type Enum8('http' = 1, 'mcp' = 2) DEFAULT 'http',
    user_id String DEFAULT '',
    api_key_id String DEFAULT '',
    record_count UInt32 DEFAULT 0,
    response_time_ms UInt32 DEFAULT 0,
    status_code UInt16 DEFAULT 200,
    error_message String DEFAULT '',
    client_ip String DEFAULT '',
    created_at DateTime DEFAULT now()
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(created_at)
ORDER BY (api_path, created_at)
SETTINGS index_granularity = 8192;
