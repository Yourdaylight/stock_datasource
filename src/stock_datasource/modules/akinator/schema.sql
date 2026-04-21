-- Akinator session archive
CREATE TABLE IF NOT EXISTS akinator_session (
    session_id String,
    user_id String,
    started_at DateTime,
    ended_at DateTime,
    question_count UInt8 DEFAULT 0,
    final_status Enum8('success'=1, 'abandoned'=2, 'timeout'=3, 'no_match'=4) DEFAULT 'abandoned',
    guessed_ts_code String DEFAULT '',
    qa_log String DEFAULT '[]',
    candidates_final String DEFAULT '[]',
    total_tokens UInt32 DEFAULT 0,
    created_date Date DEFAULT today()
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(started_at)
ORDER BY (user_id, started_at, session_id)
TTL started_at + INTERVAL 365 DAY;
