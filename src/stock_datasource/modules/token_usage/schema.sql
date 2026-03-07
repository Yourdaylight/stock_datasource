-- Token quota table: tracks each user's total quota and usage
CREATE TABLE IF NOT EXISTS user_token_quota (
    user_id String,
    total_quota Int64 DEFAULT 1000000,
    used_tokens Int64 DEFAULT 0,
    remaining_tokens Int64 DEFAULT 1000000,
    updated_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (user_id)
SETTINGS index_granularity = 8192;

-- Token usage log: records each AI conversation's token consumption
CREATE TABLE IF NOT EXISTS token_usage_log (
    id String,
    user_id String,
    session_id String DEFAULT '',
    message_id String DEFAULT '',
    agent_name String DEFAULT '',
    model_name String DEFAULT '',
    prompt_tokens Int64 DEFAULT 0,
    completion_tokens Int64 DEFAULT 0,
    total_tokens Int64 DEFAULT 0,
    created_at DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (user_id, created_at, id)
PARTITION BY toYYYYMM(created_at)
SETTINGS index_granularity = 8192;
