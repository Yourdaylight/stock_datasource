-- User LLM configuration table
CREATE TABLE IF NOT EXISTS user_llm_config (
    user_id String,
    provider String DEFAULT 'openai',
    api_key String,
    base_url String DEFAULT '',
    model_name String DEFAULT '',
    is_active UInt8 DEFAULT 1,
    updated_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (user_id, provider)
SETTINGS index_granularity = 8192;
