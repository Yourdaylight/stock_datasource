-- Financial Analysis Module - ClickHouse DDL
-- Table: report_analysis_records
-- Stores persisted AI financial report analysis results

CREATE TABLE IF NOT EXISTS report_analysis_records (
    id String,                                    -- UUID for each analysis record
    ts_code LowCardinality(String),               -- Stock code, e.g. '000001.SZ' or '00700.HK'
    stock_name String DEFAULT '',                  -- Stock name for display
    market LowCardinality(String) DEFAULT 'A',    -- Market: 'A' or 'HK'
    end_date String,                              -- Report period, e.g. '20241231'
    report_type String DEFAULT '',                -- 'annual'/'semi_annual'/'q1'/'q3'
    analysis_type String DEFAULT 'comprehensive', -- Analysis type: 'comprehensive'/'peer_comparison'/'quick'
    report_content String,                        -- Full Markdown analysis report
    data_snapshot String DEFAULT '',              -- JSON: financial data snapshot used for analysis
    health_score Float32 DEFAULT 0,               -- Overall health score (0-100)
    analysis_sections String DEFAULT '',          -- JSON: structured analysis sections
    analysis_metadata String DEFAULT '',          -- JSON: extra metadata (model version, tokens, etc.)
    created_at DateTime DEFAULT now(),
    updated_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (ts_code, end_date, analysis_type, id)
PARTITION BY toYYYYMM(created_at)
SETTINGS index_granularity = 8192;
