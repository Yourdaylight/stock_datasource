-- Users table
CREATE TABLE IF NOT EXISTS users (
    id String,
    email String,
    username String,
    password_hash String,
    is_active UInt8 DEFAULT 1,
    is_admin UInt8 DEFAULT 0,
    created_at DateTime DEFAULT now(),
    updated_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (email, id)
SETTINGS index_granularity = 8192;

-- Email whitelist table
CREATE TABLE IF NOT EXISTS email_whitelist (
    id String,
    email String,
    added_by String DEFAULT 'system',
    is_active UInt8 DEFAULT 1,
    created_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(created_at)
ORDER BY (email, id)
SETTINGS index_granularity = 8192;
