-- Arena Module Database Schema
-- ClickHouse tables for Multi-Agent Strategy Arena

-- Table: arenas - Main arena entity
CREATE TABLE IF NOT EXISTS arenas (
    id String,
    user_id String,  -- User who created this arena (for data isolation)
    name String,
    description String,
    config String,  -- JSON configuration
    state String,
    strategies String,  -- JSON array
    eliminated_strategies String,  -- JSON array
    discussion_rounds String,  -- JSON array
    current_round_id Nullable(String),
    evaluations String,  -- JSON array
    last_evaluation Nullable(DateTime64(3)),
    last_error Nullable(String),
    error_count UInt32 DEFAULT 0,
    created_at DateTime64(3) DEFAULT now64(3),
    started_at Nullable(DateTime64(3)),
    completed_at Nullable(DateTime64(3)),
    updated_at DateTime64(3) DEFAULT now64(3)
) ENGINE = MergeTree()
ORDER BY (user_id, id, created_at);

-- Table: arena_strategies - Individual strategies
CREATE TABLE IF NOT EXISTS arena_strategies (
    id String,
    arena_id String,
    user_id String,  -- User who owns this strategy (for data isolation)
    agent_id String,
    agent_role String,
    name String,
    description String,
    logic String,
    rules String,  -- JSON
    symbols Array(String),
    stage String,
    is_active UInt8 DEFAULT 1,
    eliminated_at Nullable(DateTime64(3)),
    discussion_rounds Array(String),
    refinement_history String,  -- JSON array
    backtest_result_id Nullable(String),
    simulated_positions String,  -- JSON array
    current_score Float64 DEFAULT 0,
    current_rank UInt32 DEFAULT 0,
    created_at DateTime64(3) DEFAULT now64(3),
    updated_at DateTime64(3) DEFAULT now64(3)
) ENGINE = MergeTree()
ORDER BY (user_id, arena_id, id, created_at);

-- Table: arena_thinking_messages - Thinking stream messages
CREATE TABLE IF NOT EXISTS arena_thinking_messages (
    id String,
    arena_id String,
    user_id String,  -- User who owns this message (for data isolation)
    agent_id String,
    agent_role String,
    round_id String,
    message_type String,
    content String,
    metadata String,  -- JSON
    timestamp DateTime64(3) DEFAULT now64(3)
) ENGINE = MergeTree()
ORDER BY (user_id, arena_id, timestamp)
TTL timestamp + INTERVAL 30 DAY;

-- Table: arena_discussions - Discussion rounds
CREATE TABLE IF NOT EXISTS arena_discussions (
    id String,
    arena_id String,
    user_id String,  -- User who owns this discussion (for data isolation)
    round_number UInt32,
    mode String,
    participants Array(String),
    conclusions String,  -- JSON
    started_at DateTime64(3),
    completed_at Nullable(DateTime64(3)),
    created_at DateTime64(3) DEFAULT now64(3)
) ENGINE = MergeTree()
ORDER BY (user_id, arena_id, round_number);

-- Table: arena_evaluations - Strategy evaluations
CREATE TABLE IF NOT EXISTS arena_evaluations (
    id String,
    strategy_id String,
    arena_id String,
    user_id String,  -- User who owns this evaluation (for data isolation)
    period String,
    score_return Float64,
    score_risk Float64,
    score_stability Float64,
    score_adaptability Float64,
    score_total Float64,
    rank UInt32,
    eliminated UInt8 DEFAULT 0,
    evaluated_at DateTime64(3) DEFAULT now64(3)
) ENGINE = MergeTree()
ORDER BY (user_id, arena_id, evaluated_at);

-- Index for common queries
-- Note: ClickHouse creates implicit indexes on ORDER BY columns
