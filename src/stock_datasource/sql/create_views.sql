-- Sample SQL views for common queries

-- Adjusted daily prices view
CREATE VIEW IF NOT EXISTS vw_daily_adjusted AS
SELECT 
    f.ts_code,
    f.trade_date,
    f.open * f.adj_factor as open_adj,
    f.high * f.adj_factor as high_adj,
    f.low * f.adj_factor as low_adj,
    f.close * f.adj_factor as close_adj,
    f.pre_close * f.adj_factor as pre_close_adj,
    f.change,
    f.pct_chg,
    f.vol,
    f.amount,
    f.adj_factor,
    f.created_at,
    f.updated_at
FROM fact_daily_bar f
WHERE f.adj_factor IS NOT NULL;

-- Security info with latest price
CREATE VIEW IF NOT EXISTS vw_security_latest AS
SELECT 
    s.ts_code,
    s.market,
    s.ticker,
    s.name,
    s.list_date,
    s.delist_date,
    s.status,
    d.close as latest_close,
    d.trade_date as latest_date,
    d.pct_chg as latest_change_pct
FROM dim_security s
LEFT JOIN (
    SELECT 
        ts_code,
        trade_date,
        close,
        pct_chg,
        ROW_NUMBER() OVER (PARTITION BY ts_code ORDER BY trade_date DESC) as rn
    FROM fact_daily_bar
) d ON s.ts_code = d.ts_code AND d.rn = 1
WHERE s.status = 'L';

-- Trading calendar with data availability
CREATE VIEW IF NOT EXISTS vw_trading_calendar_with_data AS
SELECT 
    cal.cal_date,
    cal.is_open,
    cal.pretrade_date,
    CASE 
        WHEN d.record_count > 0 THEN 'DATA_AVAILABLE'
        WHEN cal.is_open = 1 THEN 'MISSING_DATA'
        ELSE 'NON_TRADING_DAY'
    END as data_status,
    d.record_count
FROM (
    SELECT DISTINCT trade_date as cal_date, 1 as is_open, 
           LAG(trade_date) OVER (ORDER BY trade_date) as pretrade_date
    FROM ods_daily
) cal
LEFT JOIN (
    SELECT trade_date, COUNT(*) as record_count
    FROM ods_daily
    GROUP BY trade_date
) d ON cal.cal_date = d.trade_date
ORDER BY cal.cal_date DESC;

-- Monthly statistics
CREATE VIEW IF NOT EXISTS vw_monthly_statistics AS
SELECT 
    toYYYYMM(trade_date) as month_id,
    formatDateTime(trade_date, '%Y-%m') as month_name,
    COUNT(DISTINCT ts_code) as unique_securities,
    COUNT(*) as total_records,
    AVG(close) as avg_close_price,
    SUM(vol) as total_volume,
    SUM(amount) as total_amount
FROM fact_daily_bar
GROUP BY toYYYYMM(trade_date), formatDateTime(trade_date, '%Y-%m')
ORDER BY month_id DESC;

-- Top movers by percentage change
CREATE VIEW IF NOT EXISTS vw_top_movers AS
SELECT 
    trade_date,
    ts_code,
    close,
    pct_chg,
    vol,
    RANK() OVER (PARTITION BY trade_date ORDER BY pct_chg DESC) as rank_up,
    RANK() OVER (PARTITION BY trade_date ORDER BY pct_chg ASC) as rank_down
FROM fact_daily_bar
WHERE pct_chg IS NOT NULL;

-- Suspension analysis
CREATE VIEW IF NOT EXISTS vw_suspension_analysis AS
SELECT 
    s.trade_date,
    s.ts_code,
    s.suspend_type,
    s.suspend_reason,
    d.close as last_close_price,
    d.trade_date as last_trading_date
FROM ods_suspend_d s
LEFT JOIN (
    SELECT 
        ts_code,
        trade_date,
        close,
        ROW_NUMBER() OVER (PARTITION BY ts_code ORDER BY trade_date DESC) as rn
    FROM ods_daily
) d ON s.ts_code = d.ts_code AND d.rn = 1
ORDER BY s.trade_date DESC, s.ts_code;

-- Limit price analysis
CREATE VIEW IF NOT EXISTS vw_limit_analysis AS
SELECT 
    l.trade_date,
    l.ts_code,
    l.up_limit,
    l.down_limit,
    d.close,
    d.pre_close,
    CASE 
        WHEN d.close >= l.up_limit THEN 'HIT_UP_LIMIT'
        WHEN d.close <= l.down_limit THEN 'HIT_DOWN_LIMIT'
        ELSE 'NORMAL'
    END as limit_status
FROM ods_stk_limit l
JOIN ods_daily d ON l.trade_date = d.trade_date AND l.ts_code = d.ts_code
WHERE l.up_limit IS NOT NULL AND l.down_limit IS NOT NULL;
