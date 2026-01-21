-- Sync history table with user tracking
CREATE TABLE IF NOT EXISTS sync_history (
    task_id String,
    plugin_name String,
    task_type String,
    status String,
    records_processed UInt32 DEFAULT 0,
    error_message String DEFAULT '',
    error_traceback String DEFAULT '',
    user_id String DEFAULT '',
    username String DEFAULT '',
    started_at DateTime DEFAULT now(),
    completed_at DateTime DEFAULT now(),
    duration_seconds Float64 DEFAULT 0
) ENGINE = MergeTree()
ORDER BY (started_at, task_id)
PARTITION BY toYYYYMM(started_at)
SETTINGS index_granularity = 8192;
