-- Portfolio module database schema

-- User positions table
CREATE TABLE IF NOT EXISTS user_positions (
    id VARCHAR(50) PRIMARY KEY,
    ts_code VARCHAR(20) NOT NULL,
    stock_name VARCHAR(100) NOT NULL,
    quantity INTEGER NOT NULL,
    cost_price DECIMAL(10, 3) NOT NULL,
    buy_date DATE NOT NULL,
    current_price DECIMAL(10, 3),
    market_value DECIMAL(15, 2),
    profit_loss DECIMAL(15, 2),
    profit_rate DECIMAL(8, 4),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Index for faster queries
CREATE INDEX IF NOT EXISTS idx_user_positions_ts_code ON user_positions(ts_code);
CREATE INDEX IF NOT EXISTS idx_user_positions_buy_date ON user_positions(buy_date);

-- Portfolio analysis history
CREATE TABLE IF NOT EXISTS portfolio_analysis (
    id VARCHAR(50) PRIMARY KEY,
    analysis_date DATE NOT NULL,
    analysis_summary TEXT,
    stock_analyses JSON,
    risk_alerts JSON,
    recommendations JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for analysis queries
CREATE INDEX IF NOT EXISTS idx_portfolio_analysis_date ON portfolio_analysis(analysis_date);