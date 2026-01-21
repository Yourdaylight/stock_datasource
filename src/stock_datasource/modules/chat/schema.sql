-- Chat sessions table
CREATE TABLE IF NOT EXISTS chat_sessions (
    session_id String,
    user_id String,
    title String DEFAULT '',
    created_at DateTime DEFAULT now(),
    updated_at DateTime DEFAULT now(),
    last_message_at DateTime DEFAULT now(),
    message_count UInt32 DEFAULT 0
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (user_id, session_id)
SETTINGS index_granularity = 8192;

-- Chat messages table
CREATE TABLE IF NOT EXISTS chat_messages (
    id String,
    session_id String,
    user_id String,
    role String,
    content String,
    metadata String DEFAULT '{}',
    created_at DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (session_id, created_at, id)
PARTITION BY toYYYYMM(created_at)
SETTINGS index_granularity = 8192;
